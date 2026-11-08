import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/douyin-score-planner/scripts'))
import planner

def example():
    return {'shop_key': 'synthetic-shop', 'target': 80, 'first_future_date': '2030-01-12',
            'deadline': '2030-01-15', 'window_days': 30,
            'history': {'kind': 'aggregate', 'count': 10, 'mean': 72,
                        'first_date': '2030-01-02', 'last_date': '2030-01-11',
                        'precision': 'assumed'},
            'scenarios': [{'name': 'upper', 'daily_score': 100},
                          {'name': 'flat', 'daily_score': 70}]}

class ProjectionTests(unittest.TestCase):
    def test_required_average_and_earliest_crossing(self):
        r = planner.project(example())
        self.assertEqual(r['required_future_average'], 100)
        self.assertEqual(r['scenarios'][0]['first_target_date'], '2030-01-15')
        self.assertAlmostEqual(r['scenarios'][0]['final_mean'], 80)
        self.assertFalse(r['scenarios'][1]['meets_target'])

    def test_exact_daily_scores_roll_out_and_null_is_not_zero(self):
        c=example(); c.update(window_days=3, target=90, deadline='2030-01-13')
        c['history']={'kind':'daily','days':[{'date':'2030-01-10','score':50},
                      {'date':'2030-01-11','score':None}]}
        c['scenarios']=[{'name':'steady','daily_score':90}]
        r=planner.project(c)
        self.assertEqual(r['required_future_average'],90)
        self.assertEqual(r['scenarios'][0]['final_mean'],90)
        self.assertEqual(r['scenarios'][0]['first_target_date'],'2030-01-13')

    def test_aggregate_rollout_cannot_be_guessed(self):
        c=example();c['window_days']=12
        r=planner.project(c)
        self.assertIsNone(r['required_future_average'])
        self.assertEqual(r['scenarios'][0]['status'],'insufficient_history')

    def test_delay_can_make_deadline_impossible(self):
        c=example();c['scenarios']=[{'name':'delay','daily_score':100,'delay_days':1,'delay_score':70}]
        r=planner.project(c)
        self.assertLess(r['scenarios'][0]['final_mean'],80)
        self.assertFalse(r['scenarios'][0]['meets_target'])

    def test_unknown_rollout_cannot_claim_first_crossing_after_gap(self):
        c=example();c.update(window_days=12,deadline='2030-01-31')
        c['scenarios']=[{'name':'steady','daily_score':90}]
        r=planner.project(c)['scenarios'][0]
        self.assertEqual(r['final_mean'],90)
        self.assertIsNone(r['first_target_date'])

    def test_displayed_mean_does_not_become_verified(self):
        self.assertEqual(planner.project(example())['certainty'],'conditional')

    def test_invalid_target_and_duplicate_dates_are_rejected(self):
        c=example();c['target']=101
        with self.assertRaises(ValueError): planner.project(c)

    def test_badge_deadline_reserves_update_day(self):
        c=example();c.update(objective='black_badge',target=83,deadline='2030-01-17',badge_lag_days=1)
        r=planner.project(c)
        self.assertEqual(r['score_deadline'],'2030-01-16')
        self.assertEqual(r['future_days'],5)
        self.assertEqual(r['required_future_average'],105)
        self.assertEqual(r['constant_plan_feasibility'],'impossible_above_100')

    def test_deadline_only_and_target_only_modes(self):
        c=example();c['target']=None
        r=planner.project(c)
        self.assertIsNone(r['required_future_average'])
        self.assertEqual(r['scenarios'][0]['final_mean'],80)
        c=example();c.pop('deadline');c['horizon_days']=5
        self.assertEqual(planner.project(c)['scenarios'][0]['first_target_date'],'2030-01-15')
        c=example();c['history']={'kind':'daily','days':[{'date':'2030-01-11','score':70}]*2}
        with self.assertRaises(ValueError): planner.project(c)

class ReviewTests(unittest.TestCase):
    def row(self, star=1, signed='2030-01-01', shop='synthetic-shop'):
        return {'shop_key':shop,'order_id':'fictional-order','product_id':'fictional-product',
                'star':star,'signed':signed,'reviewed':'2030-01-02'}

    def test_duplicates_do_not_inflate_and_conflicts_stop(self):
        row=self.row()
        self.assertEqual(len(planner.merge_reviews([row,row])),1)
        with self.assertRaises(ValueError): planner.merge_reviews([row,self.row(star=5)])

    def test_shop_mixing_is_rejected(self):
        with self.assertRaises(ValueError): planner.merge_reviews([self.row(),self.row(shop='other-shop')])

    def test_signed_window_and_unscored_reviews(self):
        rows=[self.row(),dict(self.row(star=5,signed='2030-01-02'),order_id='fictional-order-2')]
        r=planner.review_summary(rows, as_of='2030-01-31')
        self.assertEqual(r['count'],1)
        self.assertEqual(r['mean'],5)

    def test_known_review_exit_does_not_assume_new_reviews(self):
        r=planner.review_summary([self.row()],as_of='2030-01-30')
        self.assertEqual(r['known_rollout'][0]['count'],1)
        self.assertEqual(r['known_rollout'][1]['count'],0)
        self.assertIsNone(r['known_rollout'][1]['mean'])

    def test_unknown_eligibility_is_not_pass(self):
        r=planner.check_gates({'brand':True,'shop_type':True})
        self.assertEqual(r['status'],'unknown')
        r=planner.check_gates({'brand':False})
        self.assertEqual(r['status'],'fail')

    def test_empty_scoring_window_still_produces_honest_report(self):
        r=planner.report(example(),{'reviews':planner.review_summary([],as_of='2030-01-31')})
        text=planner.markdown(r)
        self.assertIn('0条',text)
        self.assertIn('无计分评价',text)

    def test_explicit_star_target_is_not_a_badge_conversion(self):
        self.assertEqual(planner.minimum_five(2,6,4),2)
        self.assertIsNone(planner.minimum_five(2,6,5))

if __name__=='__main__': unittest.main()
