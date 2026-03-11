import { useState, useMemo } from "react";

const LOOPS = {
  R1:   { label:"R1 社交活力",   color:"#FF6B6B", kind:"强化链（开放）",
          desc:"N01→N02→N03  社交场所吸引聚集，聚集激活界面活跃度。E03降级为背景变量。医疗POI已纳入N01的扩展定义（医疗服务POI加权合成）。" },
  R2:   { label:"R2 步行可达",   color:"#2DD4BF", kind:"强化链（开放）",
          desc:"N04/N06→N05→N02  路网连通性与土地混合度扩大步行等时圈，可达性增加激活聚集节点，注入R1。" },
  R3:   { label:"R3 环境舒适",   color:"#38BDF8", kind:"强化链（开放）",
          desc:"N07→N08→N02  绿化遮阴提升街道舒适度，舒适留住人，聚集强度提升，注入R1。" },
  Rbad: { label:"R⁻ 交通诱导",  color:"#FF4500", kind:"恶性强化（闭合）",
          desc:"N09→N11→N10→N09  高车流→噪声污染→步行意愿下降→更多机动出行。无内置平衡，需外生干预。年轻人通勤（N_YP→N09+）为此回路的关键外部输入。" },
  R4:   { label:"R4 认知恢复",   color:"#A78BFA", kind:"强化+自限（闭合）",
          desc:"N14→N15(±倒U型)→N16→N14  内置自限的闭合回路。N_IG（代际互动）向N15注入外部激活能量，连接R5叙事主线。" },
  R5:   { label:"R5 人机共生",   color:"#34D399", kind:"强化+时滞（闭合）",
          desc:"N18→N02→N19→τ→N18  闭合强化，含时滞τ。N18通过E39（→N_IG）激活代际互动，形成R4↔R5的跨回路耦合。" },
  B2:   { label:"B2 拥挤调节",   color:"#FB923C", kind:"平衡（闭合）",
          desc:"N02(−)→N08→N02  过度聚集→拥挤效应→舒适度下降。B5文化摩擦链（N_YP→N08−）与B2共享N08节点，构成对R1的双重抑制。" },
  B4:   { label:"B4 干预疲劳",   color:"#60A5FA", kind:"平衡（闭合）",
          desc:"N18(−)→N19→N18  干预密度过高引发habituation，数据密度减少。六原型可变机制的系统动力学根据。" },
  R6:   { label:"R6 代际激活",   color:"#FBBF24", kind:"强化注入链",
          desc:"N_YP(外生)→N_IG(+)→N15(+) 且 N18→N_IG(+)→N15(+)。代际互动频率作为R4和R5的交汇节点：年轻人在场提供接触机会，人机装置（原型F社交光幕）触发互动，互动提升认知储备。" },
  cross:{ label:"跨层链路",      color:"#4a6888", kind:"跨层",
          desc:"行为层→认知干预层。N09/N11→N17，N06/N03→N14，N18→N14/N17，N_GC→N18（带娃场景驱动干预使用）。" },
};

const LOOP_ORDER = ["R1","R2","R3","Rbad","R4","R5","B2","B4","R6","cross"];
const COLOR_PRI  = ["B2","B4","Rbad","R6","R4","R5","R1","R2","R3","cross"];
const pickLoop   = function(ls) {
  return COLOR_PRI.find(function(p) { return ls.includes(p); }) || "cross";
};

// Behavior layer y≈60-310, Cognitive layer y≈400-620
const NODES = [
  // ── Behavior layer ──
  { id:"N04",  s1:"路网",   s2:"连通性",   full:"路网连通性",                            x: 60,  y:120, r:22, loops:["R2"],                         lyr:0 },
  { id:"N06",  s1:"土地",   s2:"混合度",   full:"土地混合度",                            x:100,  y:270, r:22, loops:["R2"],                         lyr:0 },
  { id:"N05",  s1:"步行",   s2:"可达性",   full:"步行可达性半径",                         x:200,  y:195, r:22, loops:["R2"],                         lyr:0 },
  { id:"N07",  s1:"绿化",   s2:"遮阴",     full:"绿化遮阴覆盖率",                         x:272,  y: 78, r:22, loops:["R3"],                         lyr:0 },
  { id:"N08",  s1:"街道",   s2:"舒适度",   full:"街道舒适度",                            x:324,  y:260, r:22, loops:["R3","B2"],                     lyr:0 },
  { id:"N01",  s1:"社交+",  s2:"医疗POI",  full:"社交场所密度（含医疗POI）",              x:450,  y: 58, r:24, loops:["R1"],                         lyr:0 },
  { id:"N02",  s1:"聚集",   s2:"强度 ★",  full:"老年人聚集强度（核心枢纽）",             x:468,  y:194, r:32, loops:["R1","R2","R3","Rbad","R5","B2"], lyr:0, hub:true },
  { id:"N03",  s1:"界面",   s2:"活跃度",   full:"街道界面活跃度",                         x:620,  y:112, r:22, loops:["R1"],                         lyr:0 },
  { id:"N10",  s1:"步行",   s2:"意愿",     full:"步行意愿（初始值0.5）",                  x:710,  y:220, r:22, loops:["Rbad"],                       lyr:0 },
  { id:"N09",  s1:"车流",   s2:"量",       full:"车流量",                               x:808,  y: 68, r:22, loops:["Rbad"],                       lyr:0 },
  { id:"N11",  s1:"噪声",   s2:"与污染",   full:"噪声与污染暴露（合并）",                  x:916,  y:178, r:24, loops:["Rbad"],                       lyr:0 },
  // ── New persona nodes (behavior layer) ──
  { id:"N_GC", s1:"隔代",   s2:"照料",     full:"隔代照料强度（带娃老人出行密度）",         x:160,  y:316, r:22, loops:["R6","cross"],                 lyr:0, persona:true },
  { id:"N_YP", s1:"年轻人", s2:"在场",     full:"年轻人白天在场密度（外生变量）",           x:720,  y:312, r:22, loops:["R6","Rbad"],                  lyr:0, exo:true },
  { id:"N_IG", s1:"代际",   s2:"互动",     full:"代际互动频率",                           x:538,  y:314, r:22, loops:["R6"],                         lyr:0, persona:true },
  // ── Cognitive / Intervention layer ──
  { id:"N14",  s1:"◆认知",  s2:"复杂度",   full:"◆ 空间认知复杂度指数",                   x:228,  y:448, r:26, loops:["R4"],                         lyr:1, dia:true },
  { id:"N16",  s1:"探索",   s2:"意愿",     full:"主动探索意愿（初始值0.5）",               x:220,  y:574, r:22, loops:["R4"],                         lyr:1 },
  { id:"N15",  s1:"认知",   s2:"储备",     full:"认知储备激活潜力",                       x:416,  y:512, r:24, loops:["R4","R6"],                     lyr:1 },
  { id:"N17",  s1:"◆生理",  s2:"压力",     full:"◆ 环境生理压力指数",                     x:606,  y:450, r:26, loops:["cross"],                      lyr:1, dia:true },
  { id:"N18",  s1:"◆人机",  s2:"干预",     full:"◆ 人机共生干预指数（设计变量）",          x:748,  y:410, r:28, loops:["R5","B4","R6"],               lyr:1, dia:true, hub:true },
  { id:"N19",  s1:"行为",   s2:"数据",     full:"行为数据密度",                           x:866,  y:514, r:22, loops:["R5","B4"],                     lyr:1 },
];
const NM = {};
NODES.forEach(function(n) { NM[n.id] = n; });

const EDGES = [
  // R1 chain
  { id:"E01", f:"N01",  t:"N02",  p:"+", loops:["R1"],         c: 0.08 },
  { id:"E02", f:"N02",  t:"N03",  p:"+", loops:["R1"],         c: 0.14 },
  { id:"E03", f:"N03",  t:"N01",  p:"+", loops:["R1"],         c: 0.10, bg:true },
  // R2 chain
  { id:"E04", f:"N04",  t:"N05",  p:"+", loops:["R2"],         c: 0.12 },
  { id:"E05", f:"N05",  t:"N02",  p:"+", loops:["R2"],         c:-0.12 },
  { id:"E06", f:"N06",  t:"N05",  p:"+", loops:["R2"],         c: 0.08 },
  // R3 chain + B2
  { id:"E07", f:"N07",  t:"N08",  p:"+", loops:["R3"],         c: 0.10 },
  { id:"E08", f:"N08",  t:"N02",  p:"+", loops:["R3","B2"],    c:-0.10 },
  // R_bad
  { id:"E09", f:"N09",  t:"N11",  p:"+", loops:["Rbad"],       c: 0.22 },
  { id:"E10", f:"N11",  t:"N10",  p:"-", loops:["Rbad"],       c: 0.16 },
  { id:"E11", f:"N10",  t:"N02",  p:"+", loops:["Rbad"],       c: 0.12 },
  { id:"E29", f:"N10",  t:"N09",  p:"-", loops:["Rbad"],       c:-0.20 },
  // R4
  { id:"E12", f:"N14",  t:"N15",  p:"+-",loops:["R4"],         c: 0.12, nl:true },
  { id:"E14", f:"N15",  t:"N16",  p:"+", loops:["R4"],         c: 0.10 },
  { id:"E15", f:"N16",  t:"N14",  p:"+", loops:["R4"],         c: 0.08 },
  // R5 + B4
  { id:"E16", f:"N18",  t:"N02",  p:"+", loops:["R5"],         c: 0.16 },
  { id:"E17", f:"N02",  t:"N19",  p:"+", loops:["R5"],         c: 0.20 },
  { id:"E18", f:"N19",  t:"N18",  p:"+", loops:["R5","B4"],    c: 0.08, delay:true },
  // B2
  { id:"E26", f:"N02",  t:"N08",  p:"-", loops:["B2"],         c: 0.20 },
  // B4
  { id:"E28", f:"N18",  t:"N19",  p:"-", loops:["B4"],         c: 0.28 },
  // Cross-layer (original)
  { id:"E13", f:"N17",  t:"N15",  p:"-", loops:["cross"],      c: 0.10, dash:true },
  { id:"E20", f:"N09",  t:"N17",  p:"+", loops:["cross"],      c: 0.08, dash:true },
  { id:"E21", f:"N11",  t:"N17",  p:"+", loops:["cross"],      c: 0.12, dash:true },
  { id:"E22", f:"N06",  t:"N14",  p:"+", loops:["cross"],      c: 0.08, dash:true },
  { id:"E23", f:"N03",  t:"N14",  p:"+", loops:["cross"],      c:-0.14, dash:true },
  { id:"E24", f:"N18",  t:"N14",  p:"+", loops:["cross","R5"], c: 0.10, dash:true },
  { id:"E25", f:"N18",  t:"N17",  p:"-", loops:["cross"],      c: 0.16, dash:true },
  // ── NEW persona edges ──
  { id:"E31", f:"N_GC", t:"N02",  p:"+", loops:["R6"],         c: 0.10 },
  { id:"E32", f:"N_GC", t:"N16",  p:"-", loops:["R6"],         c:-0.12, dash:true },
  { id:"E33", f:"N_GC", t:"N18",  p:"+", loops:["cross","R6"], c:-0.14, dash:true },
  { id:"E34", f:"N_YP", t:"N03",  p:"+", loops:["R6","Rbad"],  c: 0.14 },
  { id:"E35", f:"N_YP", t:"N09",  p:"+", loops:["Rbad"],       c:-0.16 },
  { id:"E36", f:"N_YP", t:"N08",  p:"-", loops:["B2"],         c: 0.18 },
  { id:"E37", f:"N_YP", t:"N_IG", p:"+", loops:["R6"],         c: 0.12 },
  { id:"E38", f:"N_IG", t:"N15",  p:"+", loops:["R6"],         c:-0.10, dash:true },
  { id:"E39", f:"N18",  t:"N_IG", p:"+", loops:["R6","cross"], c: 0.20, dash:true },
];

function calcEdge(e) {
  var a = NM[e.f], b = NM[e.t];
  var c = e.c || 0;
  var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
  var dx = b.x - a.x, dy = b.y - a.y;
  var L = Math.hypot(dx, dy) || 1;
  var cpx = mx + (-dy / L) * L * c;
  var cpy = my + ( dx / L) * L * c;
  var s0x = cpx - a.x, s0y = cpy - a.y;
  var sl = Math.hypot(s0x, s0y) || 1;
  var sx = a.x + (s0x / sl) * a.r;
  var sy = a.y + (s0y / sl) * a.r;
  var e0x = b.x - cpx, e0y = b.y - cpy;
  var el = Math.hypot(e0x, e0y) || 1;
  var ex = b.x - (e0x / el) * (b.r + 6);
  var ey = b.y - (e0y / el) * (b.r + 6);
  var lx = 0.25 * sx + 0.5 * cpx + 0.25 * ex;
  var ly = 0.25 * sy + 0.5 * cpy + 0.25 * ey;
  return {
    path: "M" + sx.toFixed(1) + "," + sy.toFixed(1) +
          " Q" + cpx.toFixed(1) + "," + cpy.toFixed(1) +
          " " + ex.toFixed(1) + "," + ey.toFixed(1),
    lx: lx, ly: ly,
  };
}

function Tooltip(props) {
  var n = props.node;
  if (!n) return null;
  var left = n.x > 500;
  var W = 240, H = 66;
  var tx = left ? n.x - n.r - 12 - W : n.x + n.r + 12;
  var ty = Math.max(Math.min(n.y - 26, 660 - H - 10), 10);
  var col = LOOPS[pickLoop(n.loops)].color;
  var typeTag = n.exo ? "外生变量" : n.persona ? "画像节点" : n.lyr === 0 ? "行为层" : "认知干预层";
  return (
    <g>
      <rect x={tx} y={ty} width={W} height={H} rx="5"
        fill="#0c1428" stroke="#1e3050" strokeWidth="1" opacity="0.97" />
      <text x={tx+10} y={ty+16} fill="#c8e0ff" fontSize="9" fontWeight="700" fontFamily="monospace">{n.id}</text>
      <text x={tx+48} y={ty+16} fill={col} fontSize="8" fontFamily="monospace">
        {n.full.length > 28 ? n.full.slice(0,28)+"…" : n.full}
      </text>
      <text x={tx+10} y={ty+32} fill="#3a5070" fontSize="8" fontFamily="monospace">
        {n.loops.join(" · ")}
      </text>
      <text x={tx+10} y={ty+48} fill="#283c54" fontSize="7.5" fontFamily="monospace">
        {typeTag}
        {n.dia ? " · ◆ 复合指标" : ""}
        {n.hub ? " · ★ 枢纽" : ""}
      </text>
    </g>
  );
}

export default function CLD() {
  var selState = useState(null);
  var sel = selState[0], setSel = selState[1];
  var tipState = useState(null);
  var tip = tipState[0], setTip = tipState[1];

  var edges = useMemo(function() {
    return EDGES.map(function(e) {
      var geo = calcEdge(e);
      return Object.assign({}, e, geo);
    });
  }, []);

  function toggle(k) { setSel(function(s) { return s === k ? null : k; }); }
  function eActive(e) { return !e.bg && (!sel || e.loops.includes(sel)); }
  function nActive(n) { return !sel || n.loops.includes(sel); }

  var bgEdge = edges.find(function(e) { return e.id === "E03"; });

  return (
    <div style={{
      background:"#060b18", minHeight:"100vh", display:"flex",
      flexDirection:"column", alignItems:"center", gap:"11px",
      padding:"20px 12px 28px",
      fontFamily:"'Courier New',monospace", color:"#8aa0b8",
    }}>

      {/* Header */}
      <div style={{textAlign:"center", userSelect:"none"}}>
        <div style={{fontSize:"9px",color:"#1a2c44",letterSpacing:".25em",textTransform:"uppercase"}}>
          徐家汇适老化改造 · 人机共生城市系统建模
        </div>
        <div style={{fontSize:"21px",fontWeight:"700",color:"#cfe0f8",marginTop:"4px"}}>
          因果回路图 CLD
          <span style={{fontSize:"12px",color:"#2a3c54",fontWeight:"400",marginLeft:"8px"}}>v3 · 含老年人画像与代际互动</span>
        </div>
        <div style={{fontSize:"9px",color:"#182838",marginTop:"2px",letterSpacing:".05em"}}>
          20 nodes · 36 edges · 2× closed R · 2× closed B · R⁻ · 3× open chain · R6 代际激活注入链
        </div>
      </div>

      {/* Legend strip - persona nodes */}
      <div style={{
        display:"flex",gap:"16px",flexWrap:"wrap",justifyContent:"center",
        fontSize:"9.5px",fontFamily:"monospace",
        background:"#0a1422",border:"1px solid #162030",
        borderRadius:"6px",padding:"7px 16px",maxWidth:"1020px",width:"100%",
      }}>
        <span style={{color:"#64748b"}}>节点类型：</span>
        <span><span style={{display:"inline-block",width:"10px",height:"10px",borderRadius:"50%",background:"#0d1424",border:"1.5px solid #A78BFA",marginRight:"5px",verticalAlign:"middle"}}/>普通节点</span>
        <span><span style={{display:"inline-block",width:"10px",height:"10px",borderRadius:"50%",background:"#12182e",border:"2px solid #d4930a",marginRight:"5px",verticalAlign:"middle"}}/>◆ 复合指标</span>
        <span><span style={{display:"inline-block",width:"10px",height:"10px",borderRadius:"50%",background:"#161f38",border:"2.5px solid #e8c44a",marginRight:"5px",verticalAlign:"middle"}}/>★ 枢纽</span>
        <span><span style={{display:"inline-block",width:"10px",height:"10px",borderRadius:"50%",background:"#0d1e2e",border:"2px dashed #FBBF24",marginRight:"5px",verticalAlign:"middle"}}/>👤 画像节点（v3新增）</span>
        <span><span style={{display:"inline-block",width:"10px",height:"10px",borderRadius:"50%",background:"#1a120a",border:"2px dashed #ff7830",marginRight:"5px",verticalAlign:"middle"}}/>⊕ 外生变量</span>
      </div>

      {/* SVG */}
      <div style={{
        width:"100%",maxWidth:"1020px",background:"#080e1e",
        borderRadius:"10px",border:"1px solid #162030",overflow:"hidden",
        boxShadow:"0 12px 70px #00000099",
      }}>
        <svg viewBox="0 0 1000 666" style={{width:"100%",display:"block"}}>
          <defs>
            <pattern id="dp" x="0" y="0" width="28" height="28" patternUnits="userSpaceOnUse">
              <circle cx="14" cy="14" r=".6" fill="#0e1a2c"/>
            </pattern>
            {LOOP_ORDER.map(function(k) {
              return (
                <marker key={k} id={"a-"+k} markerWidth="9" markerHeight="7" refX="8" refY="3.5" orient="auto">
                  <polygon points="0 0,9 3.5,0 7" fill={LOOPS[k].color}/>
                </marker>
              );
            })}
            <filter id="fhub">
              <feGaussianBlur stdDeviation="6" result="b"/>
              <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <filter id="fdia">
              <feGaussianBlur stdDeviation="3.5" result="b"/>
              <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <filter id="fpers">
              <feGaussianBlur stdDeviation="3" result="b"/>
              <feColorMatrix in="b" type="saturate" values="2" result="s"/>
              <feMerge><feMergeNode in="s"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <linearGradient id="sg" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%"   stopColor="#1a3050" stopOpacity="0"/>
              <stop offset="12%"  stopColor="#1a3050" stopOpacity="1"/>
              <stop offset="88%"  stopColor="#1a3050" stopOpacity="1"/>
              <stop offset="100%" stopColor="#1a3050" stopOpacity="0"/>
            </linearGradient>
            <linearGradient id="sg2" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%"   stopColor="#2a1a08" stopOpacity="0"/>
              <stop offset="12%"  stopColor="#2a1a08" stopOpacity="0.6"/>
              <stop offset="88%"  stopColor="#2a1a08" stopOpacity="0.6"/>
              <stop offset="100%" stopColor="#2a1a08" stopOpacity="0"/>
            </linearGradient>
          </defs>

          <rect width="1000" height="666" fill="url(#dp)"/>
          <rect width="1000" height="360" fill="#05080f" opacity=".38"/>
          <rect y="364" width="1000" height="302" fill="#060e0a" opacity=".22"/>

          {/* Persona zone highlight */}
          <rect x="0" y="295" width="1000" height="52" fill="url(#sg2)" opacity=".7"/>
          <text x="22" y="311" fill="#3a2010" fontSize="7.5" letterSpacing="3.5" fontFamily="monospace">PERSONA LAYER · 老年人画像节点</text>

          {/* Layer separators */}
          <line x1="0" y1="356" x2="1000" y2="356" stroke="url(#sg)" strokeWidth="1"/>
          <text x="22" y="349" fill="#122030" fontSize="8" letterSpacing="4" fontFamily="monospace">BEHAVIORAL LAYER</text>
          <text x="22" y="378" fill="#122030" fontSize="8" letterSpacing="4" fontFamily="monospace">COGNITIVE · INTERVENTION LAYER</text>

          {/* BG edge E03 */}
          {bgEdge && (
            <g opacity=".07">
              <path d={bgEdge.path} fill="none" stroke={LOOPS.R1.color}
                strokeWidth="1" strokeDasharray="5 4"
                markerEnd={"url(#a-R1)"}/>
              <text x={bgEdge.lx} y={bgEdge.ly+4} textAnchor="middle"
                fontSize="7" fill={LOOPS.R1.color} fontFamily="monospace">bkg</text>
            </g>
          )}

          {/* Edges */}
          {edges.filter(function(e){ return e.id !== "E03"; }).map(function(e) {
            var active = eActive(e);
            var lk = pickLoop(e.loops);
            var col = LOOPS[lk].color;
            var op = active ? (e.dash ? 0.55 : 0.85) : 0.04;
            var sw = active ? (e.dash ? 1.3 : 1.8) : 0.6;
            var isNeg = e.p === "-";
            var isNL  = !!e.nl;
            var dashArr = e.dash ? "8 4" : isNeg ? "4 3" : undefined;
            var badgeCol = isNeg ? "#ff7060" : isNL ? "#d4a0ff" : col;
            return (
              <g key={e.id} opacity={op}>
                <path d={e.path} fill="none" stroke={col} strokeWidth={sw}
                  strokeDasharray={dashArr}
                  markerEnd={"url(#a-"+lk+")"}/>
                <ellipse cx={e.lx} cy={e.ly} rx={isNL?8:6.5} ry="6.5"
                  fill="#080e1e" stroke={badgeCol} strokeWidth="1"/>
                <text x={e.lx} y={e.ly+3.5} textAnchor="middle"
                  fontSize={isNL?7:8.5} fill={badgeCol}
                  fontWeight="700" fontFamily="monospace">
                  {isNL ? "±" : e.p}
                </text>
                {e.delay && active && (
                  <text x={e.lx+13} y={e.ly-6} fontSize="10"
                    fill="#34D399" opacity=".85" fontFamily="monospace">τ</text>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {NODES.map(function(n) {
            var active = nActive(n);
            var lk = pickLoop(n.loops);
            var col = LOOPS[lk].color;
            var fillColor, strokeColor, strokeW, labelColor, filterAttr;
            if (n.exo) {
              fillColor = "#1a120a"; strokeColor = "#ff7830"; strokeW = 2;
              labelColor = "#ff9050"; filterAttr = "none";
            } else if (n.persona) {
              fillColor = "#0d1e2e"; strokeColor = "#FBBF24"; strokeW = 2;
              labelColor = "#FBBF24"; filterAttr = "url(#fpers)";
            } else if (n.dia) {
              fillColor = "#12182e"; strokeColor = "#d4930a"; strokeW = 1.8;
              labelColor = "#e0a828"; filterAttr = "url(#fdia)";
            } else if (n.hub) {
              fillColor = "#161f38"; strokeColor = "#e8c44a"; strokeW = 2.5;
              labelColor = "#f5d878"; filterAttr = "url(#fhub)";
            } else {
              fillColor = "#0d1424"; strokeColor = col; strokeW = 1.4;
              labelColor = col; filterAttr = "none";
            }
            var fw = (n.hub || n.dia || n.persona || n.exo) ? "700" : "400";
            var dashStroke = (n.persona || n.exo) ? "4 3" : undefined;
            return (
              <g key={n.id} opacity={active ? 1 : 0.06} style={{cursor:"pointer"}}
                onMouseEnter={function(){ setTip(n); }}
                onMouseLeave={function(){ setTip(null); }}>
                {n.dia && (
                  <rect
                    x={n.x-n.r*1.38} y={n.y-n.r*1.38}
                    width={n.r*2.76} height={n.r*2.76} rx="3"
                    fill="none" stroke="#b07808" strokeWidth="1"
                    strokeDasharray="3.5 3" opacity=".4"
                    transform={"rotate(45 "+n.x+" "+n.y+")"}/>
                )}
                <circle cx={n.x} cy={n.y} r={n.r}
                  fill={fillColor} stroke={strokeColor} strokeWidth={strokeW}
                  strokeDasharray={dashStroke}
                  filter={filterAttr}/>
                <text x={n.x} y={n.y-3} textAnchor="middle" fontSize="7.5"
                  fill={labelColor} fontWeight={fw} fontFamily="monospace">{n.s1}</text>
                <text x={n.x} y={n.y+8} textAnchor="middle" fontSize="7.5"
                  fill={labelColor} fontWeight={fw} fontFamily="monospace">{n.s2}</text>
                <text x={n.x} y={n.y-n.r+8} textAnchor="middle"
                  fill="#1e3048" fontSize="6" fontFamily="monospace">{n.id}</text>
                {n.exo && active && (
                  <text x={n.x} y={n.y+n.r+10} textAnchor="middle"
                    fill="#ff7830" fontSize="7" fontFamily="monospace">外生</text>
                )}
              </g>
            );
          })}

          <Tooltip node={tip}/>
        </svg>
      </div>

      {/* Loop buttons */}
      <div style={{display:"flex",flexWrap:"wrap",gap:"6px",justifyContent:"center",maxWidth:"1020px",width:"100%"}}>
        {LOOP_ORDER.map(function(k) {
          var d = LOOPS[k], on = sel === k;
          return (
            <button key={k} onClick={function(){ toggle(k); }} style={{
              padding:"5px 12px",borderRadius:"18px",cursor:"pointer",
              border:"1.5px solid "+(on ? d.color : "#1a2c44"),
              background:on ? d.color+"1a" : "#090f1e",
              color:on ? d.color : "#3a5268",
              fontSize:"11px",fontFamily:"monospace",
              transition:"all .15s",outline:"none",
            }}>
              <span style={{
                display:"inline-block",width:"7px",height:"7px",
                borderRadius:"50%",background:d.color,
                marginRight:"5px",verticalAlign:"middle",
              }}/>
              <span style={{fontWeight:"700",marginRight:"4px"}}>{d.kind}</span>
              <span style={{opacity:.5,fontSize:"10px"}}>{d.label}</span>
            </button>
          );
        })}
        {sel && (
          <button onClick={function(){ setSel(null); }} style={{
            padding:"5px 10px",borderRadius:"18px",cursor:"pointer",
            border:"1.5px solid #1a2c44",background:"#090f1e",
            color:"#3a5268",fontSize:"11px",fontFamily:"monospace",outline:"none",
          }}>✕ 全部</button>
        )}
      </div>

      {/* Description */}
      {sel && (
        <div style={{
          maxWidth:"1020px",width:"100%",
          padding:"10px 18px",borderRadius:"8px",
          background:"#090f1e",border:"1px solid "+LOOPS[sel].color+"28",
          fontSize:"11px",lineHeight:"1.8",color:"#6a8298",
        }}>
          <span style={{color:LOOPS[sel].color,fontWeight:"700",marginRight:"8px",fontSize:"12px"}}>
            {LOOPS[sel].label}
          </span>
          <span style={{
            display:"inline-block",padding:"1px 8px",borderRadius:"10px",
            background:LOOPS[sel].color+"14",color:LOOPS[sel].color,
            fontSize:"9.5px",marginRight:"10px",fontFamily:"monospace",
          }}>{LOOPS[sel].kind}</span>
          {LOOPS[sel].desc}
        </div>
      )}

      {/* Stats */}
      <div style={{
        display:"flex",flexWrap:"wrap",gap:"6px 16px",justifyContent:"center",
        fontSize:"9.5px",fontFamily:"monospace",
      }}>
        {[
          ["20 节点","#2a4060"],["36 条边","#2a4060"],
          ["3 画像节点（v3新增）","#FBBF24"],["1 外生变量","#ff7830"],
          ["9 条 − 边","#883030"],["1 条 ± 边","#6040a0"],["1 条 τ 边","#1a5040"],
          ["2 强化（闭合）","#9a3020"],["2 平衡（闭合）","#20508a"],
          ["3 强化链（开放）","#7a3020"],["1 恶性 R⁻","#aa2e10"],
          ["R6 代际激活","#FBBF24"],
        ].map(function(item) {
          return <span key={item[0]} style={{color:item[1]}}>{item[0]}</span>;
        })}
      </div>

    </div>
  );
}
