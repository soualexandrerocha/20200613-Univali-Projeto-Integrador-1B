// Núcleo de cálculo da maré (sem DOM): usado pela página e pelo teste em Node.
// D = {z0, frq[cph], a[m], b[m], t0_ms, passo_h, f[nós][k] (x1e5), r[nós][k] (ciclos x1e6)}
// h(t) = z0 + sum_k f_k(t) * [a_k cos(2π(r_k(t) + frq_k * t_h)) + b_k sin(...)]
// com f e r interpolados linearmente entre nós (erro < 0,01 mm frente ao UTide).
function criarMare(D) {
  const n = D.frq.length, H_MS = 3600e3;
  const w = D.frq.map(x => 2 * Math.PI * x);
  const t0 = D.t0_ms, passo = D.passo_h, nos = D.f.length;
  const ini = t0, fim = t0 + (nos - 1) * passo * H_MS;

  function altura(t_ms) {             // t_ms: instante UTC em ms
    const th = (t_ms - t0) / H_MS;
    let i = Math.floor(th / passo);
    if (i < 0 || i >= nos - 1) return NaN;
    const u = th / passo - i, f0 = D.f[i], f1 = D.f[i + 1], r0 = D.r[i], r1 = D.r[i + 1];
    let h = D.z0;
    for (let k = 0; k < n; k++) {
      const f = (f0[k] + (f1[k] - f0[k]) * u) * 1e-5;
      const r = (r0[k] + (r1[k] - r0[k]) * u) * 1e-6;
      const fase = 2 * Math.PI * r + w[k] * th;
      h += f * (D.a[k] * Math.cos(fase) + D.b[k] * Math.sin(fase));
    }
    return h;
  }

  // Preamares/baixa-mares entre t_ini e t_fim (ms UTC): amostra a cada 2 min e refina por parábola.
  function extremos(t_ini, t_fim) {
    const dt = 120e3, out = [];
    let t = t_ini - dt, y0 = altura(t), y1 = altura(t + dt);
    for (t = t_ini; t <= t_fim; t += dt) {
      const y2 = altura(t + dt);
      if ((y1 - y0 > 0) !== (y2 - y1 > 0)) {
        const den = y0 - 2 * y1 + y2;
        const d = den !== 0 ? 0.5 * (y0 - y2) / den : 0;
        out.push({ t: t + d * dt, h: y1 - 0.25 * (y0 - y2) * d, tipo: den < 0 ? 'PM' : 'BM' });
      }
      y0 = y1; y1 = y2;
    }
    return out;
  }

  return { altura, extremos, ini, fim, z0: D.z0 };
}
if (typeof module !== 'undefined') module.exports = { criarMare };
