/* Load these definitions into an authorized cua_repl session after reading its documentation.
   No OS automation, CDP, HTTP API, credentials or arbitrary selectors are used. */
var SCORE_ACTIONS = Object.freeze({
  history: {role:'按钮', label:'查看体验分历史分数趋势'},
  days30: {role:'按钮', label:'近30天'},
  close: {role:'按钮', label:'关闭'},
  reviews: {role:'按钮', label:'打开商品综合评分指标详情'},
  quality: {role:'按钮', label:'打开商品品质退货率指标详情'},
  service: {role:'按钮', label:'打开飞鸽人工会话不满意率指标详情'},
  export: {role:'按钮', label:'导出查询数据'},
  back: {role:'link', label:'Description: 商家体验分,'}
});
function findAXAction(ax, action) {
  const rule=SCORE_ACTIONS[action];
  if (!rule) throw new Error('Action is not in the read-only workflow allowlist');
  const hits=[];
  for (const line of ax.split('\n')) {
    const m=line.trim().match(/^(\d+)\s+(.+)$/);
    if (!m) continue;
    const body=m[2];
    const matches=action==='back' ? body.startsWith(rule.role+' '+rule.label) : body===rule.role+' '+rule.label;
    if (matches) hits.push(Number(m[1]));
  }
  if (hits.length!==1) throw new Error('Expected one observed '+action+' control, found '+hits.length);
  return hits[0];
}
function parseExperience(ax) {
  const out={};
  const total=ax.match(/我的总分\s+(\d+(?:\.\d+)?)\s*分/);
  if (total) out.current_score=Number(total[1]);
  const updated=ax.match(/更新时间[：:]\s*([\d/-]+)\s+(\d{2}:\d{2}:\d{2})/);
  if (updated) out.updated_at=updated[1].replaceAll('/','-')+' '+updated[2];
  for (const [label,prefix] of [['商品体验','product'],['服务体验','service']]) {
    const match=ax.match(new RegExp(label+'\\s+(\\d+(?:\\.\\d+)?)%权重\\s+(\\d+(?:\\.\\d+)?)\\s*分'));
    if (match) {out[prefix+'_weight']=Number(match[1])/100;out[prefix+'_score']=Number(match[2]);}
  }
  for (const d of [7,14,30]) {
    const m=ax.match(new RegExp('近'+d+'天平均体验分\\s+(\\d+(?:\\.\\d+)?)'));
    if (m) out['mean_'+d+'d_display']=Number(m[1]);
  }
  const range=ax.match(/(\d{4}-\d{2}-\d{2})\s+-\s+(\d{4}-\d{2}-\d{2})/);
  if (range) out.history_chart_range=[range[1],range[2]];
  return out;
}
async function scoreRead(app) {
  // A full fresh tree is mandatory: native AX indexes change after every navigation.
  return await app.getAXState({disableDiffing:true,emit:false});
}
async function scoreAction(app, action) {
  const before=await scoreRead(app);
  if (/验证码|请先登录|扫码登录/.test(before)) throw new Error('User login/verification required');
  const index=findAXAction(before,action);
  await app.click(index);
  let after=await scoreRead(app);
  // One bounded read for an explicitly observed loading state; never repeat export clicks.
  if (/页面加载中/.test(after)) after=await scoreRead(app);
  return after;
}
async function collectScoreSnapshot(app) {
  const page=await scoreRead(app);
  const result=parseExperience(page);
  if (result.current_score===undefined) throw new Error('Open the merchant experience overview first');
  await scoreAction(app,'history');
  const history=await scoreAction(app,'days30');
  Object.assign(result,parseExperience(history));
  await scoreAction(app,'close');
  result.collected_at=new Date().toISOString();
  result.channel='native-cua';
  result.history_precision='display_only_not_exact_daily_scores';
  return result;
}
function detailCount(ax, metric) {
  const label={reviews:'商品综合评分',quality:'商品品质退货率',service:'飞鸽人工会话不满意率'}[metric];
  const rows=ax.match(/共\s+(\d+)\s+条数据/);
  if (!label || !ax.includes('计算规则') || !ax.includes(label) || !rows || Number(rows[1])===0) return null;
  return Number(rows[1]);
}
async function requestScoreExport(app, metric, identityVerified) {
  if (identityVerified!==true) throw new Error('Verify the shop identity before exporting');
  if (!['reviews','quality','service'].includes(metric)) throw new Error('Unknown metric');
  const current=await scoreRead(app);
  const node={reviews:108,quality:103,service:317}[metric];
  let detail=current.includes('nodeId='+node) ? current : await scoreAction(app,metric);
  for(let i=0;i<3 && detailCount(detail,metric)===null;i++) detail=await scoreRead(app);
  if(detailCount(detail,metric)===null) throw new Error('Detail is not ready or is empty; verify before requesting export');
  const scope=detail.match(/近30天[\s\S]{0,100}?((?:\d{4}[/-]\d{2}[/-]\d{2}))[\s\S]{0,20}?((?:\d{4}[/-]\d{2}[/-]\d{2}))/);
  const rows=detailCount(detail,metric);
  const after=await scoreAction(app,'export');
  // Submission is not a completed download; the host must finish the observed export dialog
  // and use collect.py to prove a NEW complete XLSX appeared in the user's download folder.
  return {metric,requested:true,download_verified:false,
    query_rows:rows,scope:scope?[scope[1],scope[2]]:null,
    next_ui:after.split('\n').filter(x=>/导出|下载|文件|任务|确认|确定|保存|完成/.test(x)).slice(-35).join('\n')};
}
async function saveScoreDownload(app, filename) {
  if (!/^[^/\\]+\.xlsx$/.test(filename)) throw new Error('Use a unique plain XLSX filename');
  const ax=await scoreRead(app);
  if (!ax.includes('ID: save-panel')) throw new Error('No observed native save dialog');
  const field=ax.split('\n').find(x=>/文本栏 .*ID: saveAsNameTextField/.test(x));
  if (!field) throw new Error('Save filename field missing');
  await app.setValue(Number(field.trim().match(/^\d+/)[0]),filename);
  const fresh=await scoreRead(app);
  const save=fresh.split('\n').filter(x=>/按钮 保存, ID: OKButton$/.test(x));
  if (save.length!==1) throw new Error('Save control missing or ambiguous');
  await app.click(Number(save[0].trim().match(/^\d+/)[0]));
  const after=await scoreRead(app);
  if (/替换现有|是否替换|已经存在/.test(after)) throw new Error('Existing file would be replaced; cancel and choose another filename');
  return {save_clicked:true,download_verified:false};
}
if (typeof module !== 'undefined') module.exports={findAXAction,parseExperience,detailCount,collectScoreSnapshot,requestScoreExport,saveScoreDownload};
