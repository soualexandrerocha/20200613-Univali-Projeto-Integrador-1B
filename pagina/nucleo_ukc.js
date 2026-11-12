// Núcleo da folga estática sob a quilha (sem DOM): usado por pagina/folga_quilha.html
// e pelo teste ferramentas/testar_painel_ukc.py. Precisa de MARE = criarMare(D).
//
// e = {ini, fim, inst dos pontos: ms UTC; dur: min; margem, tav, tar: m; rref, rloc: t/m³;
//      fwa: mm (NaN = sem); ukcv; ukcu: 'm' | 'pct';
//      pontos: [{nome, prof, ref: 'nr'|'outro'|'inst', cota, inst}]}
//
// UKC(t) = D_NR + maré(t) − margem − T_corrigido. Uma manobra que começa em s
// é permitida se UKC ≥ exigida em todos os pontos durante [s, s + dur].
function calcularFolga(MARE, e) {
  const H_MS = 3600e3, MIN_MS = 60e3;
  const erros = [];
  const { ini, fim, dur } = e, margem = Number.isFinite(e.margem) ? e.margem : 0;
  if (!Number.isFinite(ini) || !Number.isFinite(fim)) erros.push('Informe o início e o fim do período.');
  else if (fim <= ini) erros.push('O fim do período precisa ser depois do início.');
  else if (fim - ini > 31 * 24 * H_MS) erros.push('Use um período de no máximo 31 dias.');
  else if (ini < MARE.ini || fim > MARE.fim) erros.push('O modelo cobre de 2015 a 2050.');
  if (!(dur >= 0)) erros.push('Informe a duração da manobra em minutos (0 se for instantânea).');
  if (margem < 0) erros.push('A reserva de nível não pode ser negativa.');
  const { tav, tar, rref, rloc, fwa, ukcv, ukcu } = e;
  if (!(tav > 0 && tar > 0)) erros.push('Informe os calados do navio.');
  if (!(rref >= 0.99 && rref <= 1.04) || !(rloc >= 0.99 && rloc <= 1.04)) erros.push('As densidades devem estar entre 0,990 e 1,040 t/m³.');
  if (!(ukcv >= 0)) erros.push('Informe a folga mínima exigida.');

  const pts = [];
  e.pontos.forEach((p, i) => {
    const nome = (p.nome || '').trim() || `Ponto ${i + 1}`;
    if (!(p.prof > 0)) { erros.push(`${nome}: informe a profundidade.`); return; }
    if (p.ref === 'nr') pts.push({ nome, prof: p.prof, ref: 'nr', dnr: p.prof });
    else if (p.ref === 'outro') {
      if (!Number.isFinite(p.cota)) { erros.push(`${nome}: informe a cota do zero em relação ao NR.`); return; }
      pts.push({ nome, prof: p.prof, ref: 'outro', cota: p.cota, dnr: p.prof - p.cota });
    } else {
      if (!Number.isFinite(p.inst)) { erros.push(`${nome}: informe a data e a hora da medição.`); return; }
      const hm = MARE.altura(p.inst);
      if (!Number.isFinite(hm)) { erros.push(`${nome}: data da medição fora de 2015–2050.`); return; }
      pts.push({ nome, prof: p.prof, ref: 'inst', inst: p.inst, hmed: hm, dnr: p.prof - hm });
    }
  });
  if (!e.pontos.length) erros.push('Inclua pelo menos um ponto de profundidade.');
  if (erros.length) return { erros };

  // Calado máximo corrigido pela densidade
  const tmax = Math.max(tav, tar), trim = tar - tav;
  let dT, metodo;
  if (fwa > 0) { dT = fwa / 1000 * (rref - rloc) / 0.025; metodo = `FWA ${fwa} mm`; }
  else { dT = tmax * (rref / rloc - 1); metodo = 'T·ρref/ρlocal (aprox.)'; }
  const tc = tmax + dT;
  const ukc = ukcu === 'pct' ? ukcv / 100 * tc : ukcv;
  pts.forEach(p => p.hreq = tc + ukc - p.dnr);        // maré necessária sem a reserva
  const crit = pts.reduce((a, b) => b.hreq > a.hreq ? b : a);
  const hreq = crit.hreq;

  // Maré a cada minuto, do início até fim + duração
  const durMin = Math.round(dur);
  const nStarts = Math.round((fim - ini) / MIN_MS) + 1;
  const n = nStarts + durMin;
  const h = new Float64Array(n);
  for (let i = 0; i < n; i++) h[i] = MARE.altura(ini + i * MIN_MS);

  // Janelas de início: menor maré em [s, s + dur] (fila monotônica) ≥ necessária
  function janelas(reserva) {
    const lim = hreq + reserva, out = [], dq = [];
    let a = -1, head = 0;
    for (let s = 0, j = 0; s < nStarts; s++) {
      while (j <= s + durMin) { while (dq.length > head && h[dq[dq.length - 1]] >= h[j]) dq.pop(); dq.push(j); j++; }
      while (dq[head] < s) head++;
      const ok = h[dq[head]] >= lim;
      if (ok && a < 0) a = s;
      if ((!ok || s === nStarts - 1) && a >= 0) {
        const b = ok ? s : s - 1;
        let mn = Infinity, mx = -Infinity;
        for (let k = a; k <= b + durMin; k++) { mn = Math.min(mn, h[k]); mx = Math.max(mx, h[k]); }
        out.push({ a: ini + a * MIN_MS, b: ini + b * MIN_MS, minutos: b - a + 1, hmin: mn, hmax: mx,
                   abreAntes: a === 0, fechaDepois: ok && s === nStarts - 1 });
        a = -1;
      }
    }
    return out;
  }
  const J = janelas(margem);
  const total = J.reduce((s, j) => s + j.minutos, 0);
  const ukcAt = hh => crit.dnr + hh - margem - tc;   // folga no ponto limitante
  const sens = [0, 0.10, 0.20, 0.30].map(extra => {
    const jj = janelas(margem + extra);
    return { extra, hnec: hreq + margem + extra, janelas: jj, total: jj.reduce((s, j) => s + j.minutos, 0) };
  });

  let hMinP = Infinity, hMaxP = -Infinity;
  for (let i = 0; i < nStarts; i++) { hMinP = Math.min(hMinP, h[i]); hMaxP = Math.max(hMaxP, h[i]); }
  const E = MARE.extremos(ini, fim);

  return { erros, tav, tar, tmax, trim, dT, metodo, tc, ukc, margem, durMin, pts, crit, hreq,
           hnec: hreq + margem, h, nStarts, J, total, sens, E, hMinP, hMaxP, ukcAt };
}
if (typeof module !== 'undefined') module.exports = { calcularFolga };
