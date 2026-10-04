import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

// Palette from the build guidelines: ash background, panel, char ink,
// ember for "the thing happening", husk straw, alert red.
const PALETTE = {
  ash: '#EAE6DF',
  panel: '#F6F3EE',
  ink: '#1D1B19',
  ember: '#E4572E',
  straw: '#C9A23A',
  alert: '#C8341C',
};

// Zone colour ramp: grey 30 C, straw 200, orange 400, red 550+.
const ORANGE = '#E08A3C';

function zoneColor(tempC) {
  if (tempC === null || tempC === undefined) return '#9a958d';
  if (tempC <= 30) return '#8d8a84';
  if (tempC < 200) return mix('#8d8a84', PALETTE.straw, (tempC - 30) / 170);
  if (tempC < 400) return mix(PALETTE.straw, ORANGE, (tempC - 200) / 200);
  return mix(ORANGE, PALETTE.alert, Math.min(1, (tempC - 400) / 150));
}

function mix(a, b, t) {
  const clamped = Math.max(0, Math.min(1, t));
  const pa = hexToRgb(a);
  const pb = hexToRgb(b);
  const r = Math.round(pa[0] + (pb[0] - pa[0]) * clamped);
  const g = Math.round(pa[1] + (pb[1] - pa[1]) * clamped);
  const bl = Math.round(pa[2] + (pb[2] - pa[2]) * clamped);
  return `rgb(${r},${g},${bl})`;
}

function hexToRgb(hex) {
  const h = hex.replace('#', '');
  return [
    parseInt(h.slice(0, 2), 16),
    parseInt(h.slice(2, 4), 16),
    parseInt(h.slice(4, 6), 16),
  ];
}

// Indian digit grouping: last 3, then pairs.
export function formatIN(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return 'no data';
  const [int, frac] = Math.abs(n).toString().split('.');
  let grouped;
  if (int.length <= 3) {
    grouped = int;
  } else {
    const last3 = int.slice(-3);
    const rest = int.slice(0, -3);
    grouped = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + last3;
  }
  const sign = n < 0 ? '-' : '';
  return sign + grouped + (frac ? '.' + frac : '');
}

// One hour row: {ts, running, temp_pyrolysis, feed_kg, char_kg, ...}
// as returned by the telemetry API.
export function deriveStats(hourly) {
  if (!hourly || hourly.length === 0) {
    return { running: false, runningSince: null, uptime30: null };
  }
  const last = hourly[hourly.length - 1];
  const running = Boolean(last.running);
  let runningSince = null;
  if (running) {
    for (let i = hourly.length - 1; i >= 0; i -= 1) {
      if (!hourly[i].running) break;
      runningSince = hourly[i].ts;
    }
  }
  const cutoff = Date.now() - 30 * 24 * 3600 * 1000;
  const recent = hourly.filter((h) => Date.parse(h.ts) >= cutoff);
  const runningCount = recent.filter((h) => h.running).length;
  const uptime30 = recent.length > 0 ? runningCount / recent.length : null;
  return { running, runningSince, uptime30 };
}

export default function KilnDashboard({ payload, onBack }) {
  const [selectedTs, setSelectedTs] = useState(null);
  const hourly = useMemo(() => payload?.hourly || [], [payload]);
  const events = useMemo(() => payload?.events || [], [payload]);

  const latestTs = hourly.length ? hourly[hourly.length - 1].ts : null;
  const cursorTs = selectedTs || latestTs;

  const stats = useMemo(() => deriveStats(hourly), [hourly]);

  const row = useMemo(
    () => hourly.find((h) => h.ts === cursorTs) || hourly[hourly.length - 1] || null,
    [hourly, cursorTs],
  );

  const cumulativeChar = useMemo(() => {
    const total = hourly.reduce((sum, h) => sum + (h.char_kg || 0), 0);
    return total;
  }, [hourly]);

  const todayChar = useMemo(() => {
    if (!row) return 0;
    const day = row.ts.slice(0, 10);
    return hourly
      .filter((h) => h.ts.slice(0, 10) === day)
      .reduce((sum, h) => sum + (h.char_kg || 0), 0);
  }, [hourly, row]);

  const statusLabel = stats.running
    ? `Running for ${hoursSince(stats.runningSince)}`
    : 'Stopped';

  const quality = row?.quality ?? 1;
  const lowQuality = quality < 0.9;

  if (!hourly.length) {
    return (
      <div className="min-h-screen bg-[#EAE6DF] text-[#1D1B19] p-8">
        <div className="mx-auto max-w-3xl rounded-xl border border-black/10 bg-white/60 p-8 backdrop-blur">
          <h1 className="text-2xl font-semibold">{payload?.name || 'Kiln telemetry'}</h1>
          <p className="mt-2 text-sm">No telemetry has been received yet.</p>
          <button
            type="button"
            onClick={onBack}
            className="mt-6 rounded-lg border border-black/15 px-4 py-2 text-sm"
          >
            Back to dataroom
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#EAE6DF] text-[#1D1B19] p-4 sm:p-6">
      <div className="mx-auto max-w-6xl space-y-4">
        <header className="flex flex-wrap items-baseline justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">{payload?.name || 'Kiln 1'}</h1>
            <p className="text-sm text-black/60">
              Rice husk pyrolysis{payload?.location ? ` · ${payload.location}` : ''}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span
              className="rounded-full border px-3 py-1 text-sm"
              style={{
                borderColor: stats.running ? PALETTE.ember : 'rgba(0,0,0,.2)',
                color: stats.running ? PALETTE.ember : PALETTE.ink,
                background: 'rgba(255,255,255,.55)',
              }}
            >
              {statusLabel}
            </span>
            <button
              type="button"
              onClick={onBack}
              className="rounded-lg border border-black/15 bg-white/60 px-3 py-1.5 text-sm backdrop-blur"
            >
              Back
            </button>
          </div>
        </header>

        {payload?.is_simulated && (
          <div className="rounded-lg border border-black/10 bg-white/60 px-4 py-2 text-sm backdrop-blur">
            Simulated data. These readings are not from a calibrated instrument.
          </div>
        )}

        {lowQuality && (
          <div
            className="rounded-lg border px-4 py-2 text-sm backdrop-blur"
            style={{ borderColor: PALETTE.alert, color: PALETTE.alert, background: 'rgba(255,255,255,.7)' }}
          >
            Data completeness {Math.round(quality * 100)}% for this hour. Some
            expected readings are missing.
          </div>
        )}

        <Scrubber
          hourly={hourly}
          cursorTs={cursorTs}
          onChange={setSelectedTs}
          isLive={!selectedTs}
          onLive={() => setSelectedTs(null)}
        />

        <KilnSchematic row={row} stats={stats} todayChar={todayChar} />

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Kpi label="30-day uptime" value={pct(stats.uptime30)} emphasis />
          <Kpi label="Husk fed today" value={`${formatIN(row?.feed_kg)} kg`} />
          <Kpi label="Biochar made today" value={`${formatIN(todayChar)} kg`} />
          <Kpi label="Yield today" value={yieldToday(hourly, row)} />
          <Kpi
            label="CO₂e removed to date"
            value={co2e(cumulativeChar, payload)}
          />
          <Kpi
            label="Syngas flow"
            value={row?.syngas_nm3h != null ? `${formatIN(Math.round(row.syngas_nm3h))} Nm³/h` : 'no data'}
          />
        </div>

        <div className="grid gap-3 lg:grid-cols-2">
          <Gauge
            label="Pyrolysis temperature"
            value={row?.temp_pyrolysis}
            unit="°C"
            min={0}
            max={700}
            band={[450, 550]}
            outOfBand={row?.running && row?.temp_pyrolysis != null && (row.temp_pyrolysis < 450 || row.temp_pyrolysis > 550)}
          />
          <Gauge
            label="Feed rate"
            value={row?.feed_kg}
            unit="kg/h"
            min={0}
            max={300}
          />
          <Gauge
            label="Biochar output"
            value={row?.char_kg}
            unit="kg/h"
            min={0}
            max={150}
          />
          <Gauge
            label="Drum speed"
            value={row?.drum_rpm}
            unit="rpm"
            min={0}
            max={20}
          />
        </div>

        <TemperatureChart hourly={hourly} cursorTs={cursorTs} />

        <EventLog events={events} cursorTs={cursorTs} onPick={setSelectedTs} />

        <footer className="pt-2 pb-8 text-xs text-black/55">
          {payload?.co2e_factor_t_per_t != null ? (
            <span>
              CO₂e factor {payload.co2e_factor_t_per_t} t per t biochar
              {payload.co2e_factor_source ? ` · source: ${payload.co2e_factor_source}` : ''}
            </span>
          ) : (
            <span>
              CO₂e removed is not shown: no verified MRV factor is configured for
              this project.
            </span>
          )}
          {payload?.generated_at && (
            <span> · Data received {new Date(payload.generated_at).toLocaleString('en-IN')}</span>
          )}
        </footer>
      </div>
    </div>
  );
}

function hoursSince(ts) {
  if (!ts) return 'a while';
  const hours = Math.max(0, Math.round((Date.now() - Date.parse(ts)) / 3600000));
  return `${hours} h`;
}

function pct(v) {
  return v == null ? 'no data' : `${Math.round(v * 100)}%`;
}

function yieldToday(hourly, row) {
  if (!row) return 'no data';
  const day = row.ts.slice(0, 10);
  const rows = hourly.filter((h) => h.ts.slice(0, 10) === day);
  const feed = rows.reduce((s, h) => s + (h.feed_kg || 0), 0);
  const char = rows.reduce((s, h) => s + (h.char_kg || 0), 0);
  if (!feed) return 'no data';
  return `${((char / feed) * 100).toFixed(1)}%`;
}

function co2e(totalCharKg, payload) {
  const factor = payload?.co2e_factor_t_per_t;
  if (factor == null) return 'no factor';
  const tonnes = totalCharKg / 1000;
  return `${(tonnes * factor).toFixed(1)} t`;
}

function Kpi({ label, value, emphasis }) {
  return (
    <div
      className={`rounded-xl border border-black/10 bg-white/55 p-3 backdrop-blur ${emphasis ? 'ring-1 ring-[#E4572E]/40' : ''}`}
    >
      <div className="text-xs text-black/60">{label}</div>
      <div className="mt-1 text-xl font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function Scrubber({ hourly, cursorTs, onChange, isLive, onLive }) {
  const first = hourly[0].ts;
  const last = hourly[hourly.length - 1].ts;
  const firstMs = Date.parse(first);
  const lastMs = Date.parse(last);
  const cursorMs = cursorTs ? Date.parse(cursorTs) : lastMs;
  const step = lastMs > firstMs ? (cursorMs - firstMs) / (lastMs - firstMs) : 0;

  // Play replays the last ~2 weeks quickly, then stops at live. Moving
  // the slider stops playback, per the spec's core interaction.
  const playRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);

  const stopPlay = useCallback(() => {
    if (playRef.current) {
      window.clearInterval(playRef.current);
      playRef.current = null;
    }
    setIsPlaying(false);
  }, []);

  useEffect(() => stopPlay, [stopPlay]);

  const startPlay = useCallback(() => {
    const span = lastMs - firstMs;
    const replayMs = Math.min(span, 14 * 24 * 3600 * 1000);
    const from = Math.max(firstMs, lastMs - replayMs);
    let cursor = from;
    setIsPlaying(true);
    playRef.current = window.setInterval(() => {
      cursor += 6 * 3600 * 1000; // 6 h per tick, ~2 s for two weeks
      if (cursor >= lastMs) {
        onLive();
        stopPlay();
        return;
      }
      onChange(new Date(cursor).toISOString());
    }, 60);
  }, [firstMs, lastMs, onChange, onLive, stopPlay]);

  const handleSlider = (e) => {
    stopPlay();
    const frac = Number(e.target.value) / 1000;
    const ts = new Date(firstMs + frac * (lastMs - firstMs));
    onChange(ts.toISOString());
  };

  return (
    <div className="sticky top-0 z-20 rounded-xl border border-black/10 bg-white/70 p-3 backdrop-blur">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onLive}
          className="rounded-lg border px-3 py-1 text-sm"
          style={{
            borderColor: isLive ? PALETTE.ember : 'rgba(0,0,0,.2)',
            color: isLive ? PALETTE.ember : PALETTE.ink,
          }}
        >
          Live
        </button>
        <button
          type="button"
          onClick={isPlaying ? stopPlay : startPlay}
          className="rounded-lg border px-3 py-1 text-sm"
          style={{
            borderColor: isPlaying ? PALETTE.ember : 'rgba(0,0,0,.2)',
            color: isPlaying ? PALETTE.ember : PALETTE.ink,
          }}
        >
          {isPlaying ? 'Pause' : 'Play'}
        </button>
        <input
          type="range"
          min={0}
          max={1000}
          value={Math.round(step * 1000)}
          onChange={handleSlider}
          className="flex-1"
          aria-label="Select a moment in the past year"
        />
        <span className="w-40 shrink-0 text-right text-xs tabular-nums text-black/70">
          {cursorTs ? new Date(cursorTs).toLocaleString('en-IN') : 'live'}
        </span>
      </div>
    </div>
  );
}

function KilnSchematic({ row, stats, todayChar }) {
  const running = Boolean(stats.running);
  const pyro = row?.temp_pyrolysis ?? null;
  const outOfRange = running && pyro != null && (pyro < 450 || pyro > 550);

  return (
    <div className="rounded-xl border border-black/10 bg-white/55 p-4 backdrop-blur">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium">Kiln schematic</span>
        {!running && (
          <span
            className="rounded border px-2 py-0.5 text-xs"
            style={{ borderColor: PALETTE.alert, color: PALETTE.alert }}
          >
            Kiln stopped
          </span>
        )}
      </div>
      <svg viewBox="0 0 640 200" className="w-full" role="img" aria-label="Rotary kiln process diagram">
        {/* Hopper */}
        <polygon points="30,40 90,40 78,110 42,110" fill="#d8d3ca" stroke="#1D1B19" strokeWidth="1.5" />
        <text x="60" y="130" textAnchor="middle" fontSize="11" fill="#1D1B19">Husk hopper</text>
        {/* Feeder */}
        <rect x="90" y="86" width="60" height="18" fill="#cfc9bf" stroke="#1D1B19" strokeWidth="1.5" />
        <text x="120" y="130" textAnchor="middle" fontSize="11" fill="#1D1B19">Screw feeder</text>

        {/* Rotary drum, three zones coloured by temperature */}
        <rect x="150" y="70" width="140" height="52" fill={zoneColor(row?.temp_drying)} stroke="#1D1B19" strokeWidth="1.5" />
        <rect x="290" y="70" width="140" height="52" fill={zoneColor(pyro)} stroke="#1D1B19" strokeWidth={outOfRange ? 3 : 1.5} />
        <rect
          x="430" y="70" width="90" height="52"
          fill={zoneColor(row?.temp_finishing)}
          stroke="#1D1B19"
          strokeWidth="1.5"
        />
        {outOfRange && (
          <rect x="290" y="70" width="140" height="52" fill="none" stroke={PALETTE.alert} strokeWidth="3" />
        )}

        {/* Drum rotation marks - only when running */}
        {running && (
          <g className="drum-motion">
            {Array.from({ length: 12 }).map((_, i) => (
              <line
                key={i}
                x1={160 + i * 36}
                y1="70"
                x2={160 + i * 36}
                y2="122"
                stroke="rgba(29,27,25,.35)"
                strokeWidth="2"
              />
            ))}
          </g>
        )}

        {/* Zone chips above the drum with leader lines */}
        <Chip x={220} label="Drying" value={row?.temp_drying} />
        <Chip x={360} label="Pyrolysis" value={pyro} />
        <Chip x={475} label="Finishing" value={row?.temp_finishing} />

        {/* Discharge hood + biochar pile */}
        <polygon points="520,70 570,70 570,122 520,122" fill="#d8d3ca" stroke="#1D1B19" strokeWidth="1.5" />
        <path
          d={`M 545 122 q ${Math.min(45, 8 + todayChar / 40)} ${-Math.min(48, 10 + todayChar / 35)} ${Math.min(90, 16 + todayChar / 20)} 0 z`}
          fill="#3a3733"
        />
        <text x="565" y="150" textAnchor="middle" fontSize="11" fill="#1D1B19">Biochar</text>

        {/* Syngas loop: hood -> cyclone -> burner -> jacket */}
        <path d="M 545 70 C 545 30, 470 24, 420 30" fill="none" stroke="#1D1B19" strokeWidth="1.5" strokeDasharray="4 3" />
        <circle cx="405" cy="34" r="14" fill="#e4dfd7" stroke="#1D1B19" strokeWidth="1.5" />
        <text x="405" y="20" textAnchor="middle" fontSize="10" fill="#1D1B19">Cyclone</text>

        {row?.syngas_nm3h > 0 && (
          <g>
            <path d="M 300 34 q 10 -14 0 -24 q -8 10 0 24" fill={PALETTE.ember} />
            <text x="300" y="58" textAnchor="middle" fontSize="10" fill="#1D1B19">Burner</text>
          </g>
        )}

        <rect x="150" y="128" width="370" height="8" fill={running ? PALETTE.ember : '#b9b3a9'} opacity="0.55" />
        <text x="335" y="152" textAnchor="middle" fontSize="10" fill="#1D1B19">Heating jacket</text>

        {/* Flue stack */}
        <rect x="470" y="0" width="12" height="34" fill="#cfc9bf" stroke="#1D1B19" strokeWidth="1.5" />
        {running && row?.syngas_nm3h > 0 && (
          <path d="M 476 0 q -8 -12 0 -20 q 8 8 0 20" fill="rgba(29,27,25,.35)" />
        )}

        {/* Colour legend - always shown */}
        <g transform="translate(20,168)">
          <rect x="0" y="0" width="14" height="14" fill="#8d8a84" />
          <text x="20" y="11" fontSize="10" fill="#1D1B19">30 °C</text>
          <rect x="70" y="0" width="14" height="14" fill={PALETTE.straw} />
          <text x="90" y="11" fontSize="10" fill="#1D1B19">200 °C</text>
          <rect x="150" y="0" width="14" height="14" fill={ORANGE} />
          <text x="170" y="11" fontSize="10" fill="#1D1B19">400 °C</text>
          <rect x="230" y="0" width="14" height="14" fill={PALETTE.alert} />
          <text x="250" y="11" fontSize="10" fill="#1D1B19">550 °C and above</text>
        </g>
      </svg>
    </div>
  );
}

function Chip({ x, label, value }) {
  const text = value == null ? 'no data' : `${Math.round(value)} °C`;
  return (
    <g>
      <line x1={x} y1="56" x2={x} y2="70" stroke="rgba(29,27,25,.5)" strokeWidth="1" />
      <rect x={x - 34} y="34" width="68" height="22" rx="4" fill="rgba(255,255,255,.85)" stroke="rgba(0,0,0,.15)" />
      <text x={x} y="44" textAnchor="middle" fontSize="9" fill="#1D1B19">{label}</text>
      <text x={x} y="53" textAnchor="middle" fontSize="9" fontWeight="600" fill="#1D1B19">{text}</text>
    </g>
  );
}

function Gauge({ label, value, unit, min = 0, max = 100, band, outOfBand }) {
  const hasValue = value != null;
  const frac = hasValue ? Math.max(0, Math.min(1, (value - min) / (max - min))) : 0;
  const bandStart = band ? (band[0] - min) / (max - min) : null;
  const bandEnd = band ? (band[1] - min) / (max - min) : null;
  const color = outOfBand ? PALETTE.alert : PALETTE.ember;

  return (
    <div className="rounded-xl border border-black/10 bg-white/55 p-4 backdrop-blur">
      <div className="text-xs text-black/60">{label}</div>
      <div
        className="mt-1 text-2xl font-semibold tabular-nums"
        style={{ color: hasValue ? PALETTE.ink : 'rgba(0,0,0,.4)' }}
      >
        {hasValue ? formatIN(Math.round(value)) : 'no data'}
        {hasValue && <span className="ml-1 text-sm font-normal text-black/55">{unit}</span>}
      </div>
      <div className="relative mt-3 h-2 rounded-full bg-black/10">
        {band && (
          <div
            className="absolute inset-y-0 rounded-full"
            style={{
              left: `${Math.max(0, bandStart) * 100}%`,
              width: `${Math.min(1, bandEnd - Math.max(0, bandStart)) * 100}%`,
              background: 'rgba(201,162,58,.55)',
            }}
          />
        )}
        {hasValue && (
          <div
            className="absolute inset-y-0 left-0 rounded-full"
            style={{ width: `${frac * 100}%`, background: color }}
          />
        )}
      </div>
      {band && (
        <div className="mt-1 text-[10px] text-black/50">
          target band {band[0]} to {band[1]} {unit}
        </div>
      )}
      {outOfBand && (
        <div className="mt-1 text-[11px]" style={{ color: PALETTE.alert }}>
          outside the target band
        </div>
      )}
    </div>
  );
}

function TemperatureChart({ hourly, cursorTs }) {
  const width = 420;
  const height = 160;
  const pad = { l: 34, r: 8, t: 10, b: 20 };

  // Default window: last 48 h of the data we hold.
  const cursorMs = cursorTs ? Date.parse(cursorTs) : Date.parse(hourly[hourly.length - 1].ts);
  const windowStart = cursorMs - 48 * 3600 * 1000;
  const points = hourly.filter((h) => {
    const ms = Date.parse(h.ts);
    return ms >= windowStart && ms <= cursorMs;
  });

  if (points.length < 2) {
    return (
      <Panel title="Temperature by zone" readout="Not enough data in this 48 h window.">
        <div className="p-6 text-sm text-black/55">no data</div>
      </Panel>
    );
  }

  const minY = 0;
  const maxY = 700;
  const xs = (i) => pad.l + (i / (points.length - 1)) * (width - pad.l - pad.r);
  const ys = (v) => height - pad.b - ((v - minY) / (maxY - minY)) * (height - pad.t - pad.b);

  const line = (field) =>
    points
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${xs(i).toFixed(1)} ${ys(p[field] ?? 0).toFixed(1)}`)
      .join(' ');

  const bandTop = ys(550);
  const bandBottom = ys(450);
  const last = points[points.length - 1];

  return (
    <Panel
      title="Temperature by zone"
      readout={
        last.temp_pyrolysis != null
          ? `Pyrolysis ${Math.round(last.temp_pyrolysis)} °C over the last 48 hours.`
          : 'No pyrolysis readings in this window.'
      }
    >
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Zone temperatures over 48 hours">
        <rect
          x={pad.l} y={bandTop} width={width - pad.l - pad.r} height={bandBottom - bandTop}
          fill="rgba(201,162,58,.3)"
        />
        <text x={width - pad.r - 2} y={bandTop + 11} textAnchor="end" fontSize="9" fill="rgba(29,27,25,.6)">
          target 450-550
        </text>
        {[0, 200, 400, 600].map((v) => (
          <g key={v}>
            <line x1={pad.l} y1={ys(v)} x2={width - pad.r} y2={ys(v)} stroke="rgba(0,0,0,.08)" />
            <text x={pad.l - 5} y={ys(v) + 3} textAnchor="end" fontSize="9" fill="rgba(0,0,0,.5)">{v}</text>
          </g>
        ))}
        <path d={line('temp_drying')} fill="none" stroke="#8d8a84" strokeWidth="1.5" />
        <path d={line('temp_pyrolysis')} fill="none" stroke={PALETTE.ember} strokeWidth="2" />
        <path d={line('temp_finishing')} fill="none" stroke={PALETTE.straw} strokeWidth="1.5" />
        <line
          x1={xs(points.length - 1)} y1={pad.t} x2={xs(points.length - 1)} y2={height - pad.b}
          stroke={PALETTE.ember} strokeDasharray="3 3"
        />
        <text x={pad.l} y={height - 6} fontSize="9" fill="rgba(0,0,0,.5)">
          {new Date(points[0].ts).toLocaleDateString('en-IN')}
        </text>
        <text x={width - pad.r} y={height - 6} textAnchor="end" fontSize="9" fill="rgba(0,0,0,.5)">
          {new Date(points[points.length - 1].ts).toLocaleDateString('en-IN')}
        </text>
      </svg>
      <div className="mt-1 flex flex-wrap gap-3 text-[10px] text-black/60">
        <span><span style={{ color: '#8d8a84' }}>■</span> drying</span>
        <span><span style={{ color: PALETTE.ember }}>■</span> pyrolysis</span>
        <span><span style={{ color: PALETTE.straw }}>■</span> finishing</span>
      </div>
    </Panel>
  );
}

function EventLog({ events, cursorTs, onPick }) {
  const cursorMs = cursorTs ? Date.parse(cursorTs) : Date.now();
  const before = events
    .filter((e) => Date.parse(e.ts) <= cursorMs)
    .slice(-6)
    .reverse();

  return (
    <Panel
      title="Event log"
      readout={before.length ? 'Last six events before the selected moment.' : 'No events recorded yet.'}
    >
      <ul className="divide-y divide-black/5">
        {before.map((e, i) => (
          <li key={`${e.ts}-${i}`}>
            <button
              type="button"
              onClick={() => onPick(e.ts)}
              className="flex w-full items-baseline justify-between gap-3 px-4 py-2 text-left text-sm hover:bg-black/[.03]"
            >
              <span style={{ color: e.kind === 'out_of_range' ? PALETTE.alert : PALETTE.ink }}>
                {labelFor(e.kind)}
                {e.detail ? ` - ${e.detail}` : ''}
              </span>
              <span className="shrink-0 text-xs tabular-nums text-black/55">
                {new Date(e.ts).toLocaleString('en-IN')}
              </span>
            </button>
          </li>
        ))}
        {!before.length && (
          <li className="px-4 py-3 text-sm text-black/55">no data</li>
        )}
      </ul>
    </Panel>
  );
}

function labelFor(kind) {
  if (kind === 'started') return 'Kiln started';
  if (kind === 'stopped') return 'Kiln stopped';
  return 'Temperature out of range';
}

function Panel({ title, readout, children }) {
  return (
    <div className="rounded-xl border border-black/10 bg-white/55 p-4 backdrop-blur">
      <div className="text-sm font-medium">{title}</div>
      <div className="mt-0.5 text-xs text-black/60">{readout}</div>
      <div className="mt-2">{children}</div>
    </div>
  );
}
