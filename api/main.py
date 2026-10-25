import sys
from pathlib import Path
from typing import Optional

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from rating_engine import get_goal_elo_results

app = FastAPI(
    title="WAGD - Premier League Goal-Elo Rating System",
    description="Dynamic football team ratings based on goal-by-goal zero-sum exchanges.",
    version="1.0.0",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cached rating results
_CACHED_DATA = None


def get_cached_ratings():
    global _CACHED_DATA
    if _CACHED_DATA is None:
        _CACHED_DATA = get_goal_elo_results()
    return _CACHED_DATA


@app.get("/api/summary")
def get_summary():
    data = get_cached_ratings()
    leaderboard = data["leaderboard"]
    biggest_climber = max(leaderboard, key=lambda x: x["delta_total"])
    biggest_dropper = min(leaderboard, key=lambda x: x["delta_total"])
    top_team = leaderboard[0]

    return {
        "total_matches": data["total_matches"],
        "base_rating": data["base_rating"],
        "k_factor": data["k_factor"],
        "top_rated": top_team,
        "biggest_climber": biggest_climber,
        "biggest_dropper": biggest_dropper,
        "total_teams": len(leaderboard),
    }


@app.get("/api/leaderboard")
def get_leaderboard():
    data = get_cached_ratings()
    return {"leaderboard": data["leaderboard"]}


@app.get("/api/history")
def get_history(team: Optional[str] = None):
    data = get_cached_ratings()
    histories = data["team_histories"]
    if team:
        if team not in histories:
            raise HTTPException(status_code=404, detail=f"Team '{team}' not found.")
        return {"team": team, "history": histories[team]}
    return {"histories": histories}


@app.get("/api/matches")
def get_matches(limit: int = 50, team: Optional[str] = None):
    data = get_cached_ratings()
    matches = data["processed_matches"]
    if team:
        matches = [m for m in matches if m["home_team"] == team or m["away_team"] == team]
    return {"total": len(matches), "matches": matches[:limit]}


@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    """Serves an interactive dashboard with Chart.js and Tailwind CSS."""
    return """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WAGD | Premier League Goal-Elo Ratings</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#f0fdf4',
              500: '#22c55e',
              600: '#16a34a',
              900: '#14532d',
            }
          }
        }
      }
    }
  </script>
  <style>
    body { background-color: #0b0f19; color: #f3f4f6; font-family: system-ui, -apple-system, sans-serif; }
    .glass-card { background: rgba(17, 24, 39, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(55, 65, 81, 0.5); }
    /* Custom scrollbar */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-thumb { background: #374151; border-radius: 3px; }
  </style>
</head>
<body class="min-h-screen">
  <!-- Header -->
  <header class="border-b border-gray-800 bg-gray-900/50 backdrop-blur sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-black text-lg">
          ⚽
        </div>
        <div>
          <h1 class="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            WAGD <span class="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Goal-Elo</span>
          </h1>
          <p class="text-xs text-gray-400">Premier League Dynamic Ratings (1v1 Goal Exchange)</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <a href="/" class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
          Dashboard
        </a>
        <a href="/methodology" class="text-xs font-medium text-gray-400 hover:text-white transition px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700">
          Methodology
        </a>
        <a href="/docs" target="_blank" class="text-xs font-medium text-gray-400 hover:text-white transition px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700">
          API Docs
        </a>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
    <!-- KPI Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="kpi-container">
      <div class="glass-card rounded-xl p-5 shadow-lg">
        <div class="text-xs font-medium uppercase tracking-wider text-gray-400">#1 Top Rated Team</div>
        <div class="text-2xl font-black mt-1 text-white" id="kpi-top-team">...</div>
        <div class="text-xs mt-2 text-emerald-400 flex items-center gap-1" id="kpi-top-rating">...</div>
      </div>
      <div class="glass-card rounded-xl p-5 shadow-lg">
        <div class="text-xs font-medium uppercase tracking-wider text-gray-400">Biggest Climber</div>
        <div class="text-2xl font-black mt-1 text-emerald-400" id="kpi-climber-team">...</div>
        <div class="text-xs mt-2 text-gray-400" id="kpi-climber-delta">...</div>
      </div>
      <div class="glass-card rounded-xl p-5 shadow-lg">
        <div class="text-xs font-medium uppercase tracking-wider text-gray-400">Biggest Dropper</div>
        <div class="text-2xl font-black mt-1 text-rose-400" id="kpi-dropper-team">...</div>
        <div class="text-xs mt-2 text-gray-400" id="kpi-dropper-delta">...</div>
      </div>
      <div class="glass-card rounded-xl p-5 shadow-lg">
        <div class="text-xs font-medium uppercase tracking-wider text-gray-400">Matches Processed</div>
        <div class="text-2xl font-black mt-1 text-indigo-400" id="kpi-matches">380</div>
        <div class="text-xs mt-2 text-gray-400">Base: 1000 | K-Factor: 15.0</div>
      </div>
    </div>

    <!-- Interactive Trajectory Chart -->
    <div class="glass-card rounded-2xl p-6 shadow-xl">
      <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-gray-800">
        <div>
          <h2 class="text-lg font-bold text-white">Rating Trajectories Across 38 Matchdays</h2>
          <p class="text-xs text-gray-400">Click any team in the legend or filters to isolate their progress over the season</p>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <button onclick="filterPresets('all')" class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition">Show All</button>
          <button onclick="filterPresets('top5')" class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition">Top 5</button>
          <button onclick="filterPresets('bottom5')" class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition">Bottom 5</button>
          <button onclick="filterPresets('big6')" class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition">Traditional Big 6</button>
          <button onclick="filterPresets('none')" class="text-xs px-2.5 py-1 rounded bg-gray-800 hover:bg-gray-700 text-gray-300 border border-gray-700 transition">Clear</button>
        </div>
      </div>
      <div class="h-[460px] w-full pt-4">
        <canvas id="ratingsChart"></canvas>
      </div>
    </div>

    <!-- Leaderboard Table & Big Upsets -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Leaderboard -->
      <div class="lg:col-span-2 glass-card rounded-2xl p-6 shadow-xl">
        <div class="flex items-center justify-between pb-4 border-b border-gray-800">
          <div>
            <h2 class="text-lg font-bold text-white">Goal-Elo Leaderboard</h2>
            <p class="text-xs text-gray-400">Final table sorted by zero-sum ratings after Matchday 38</p>
          </div>
        </div>
        <div class="overflow-x-auto mt-4">
          <table class="w-full text-left text-sm text-gray-300">
            <thead class="text-xs uppercase bg-gray-900/60 text-gray-400">
              <tr>
                <th class="py-3 px-3">#</th>
                <th class="py-3 px-3">Team</th>
                <th class="py-3 px-3 text-right">Rating</th>
                <th class="py-3 px-3 text-right">Net Change</th>
                <th class="py-3 px-3 text-center">P</th>
                <th class="py-3 px-3 text-center">GF</th>
                <th class="py-3 px-3 text-center">GA</th>
                <th class="py-3 px-3 text-center">GD</th>
              </tr>
            </thead>
            <tbody id="leaderboard-body" class="divide-y divide-gray-800">
              <!-- Populated via JS -->
            </tbody>
          </table>
        </div>
      </div>

      <!-- Top Rating Swing Matches -->
      <div class="glass-card rounded-2xl p-6 shadow-xl space-y-4">
        <div class="border-b border-gray-800 pb-3">
          <h2 class="text-lg font-bold text-white">Major Rating Swings</h2>
          <p class="text-xs text-gray-400">Matches with the largest rating transfers</p>
        </div>
        <div id="swings-container" class="space-y-3 overflow-y-auto max-h-[500px] pr-1">
          <!-- Populated via JS -->
        </div>
      </div>
    </div>
  </main>

  <footer class="mt-16 border-t border-gray-800 py-6 text-center text-xs text-gray-500">
    WAGD Football Analytics Engine • Built with FastAPI, Chart.js & Tailwind CSS
  </footer>

  <script>
    const TEAM_COLORS = {
      'Arsenal': '#ef4444',
      'Aston Villa': '#881337',
      'Bournemouth': '#dc2626',
      'Brentford': '#ea580c',
      'Brighton': '#0284c7',
      'Burnley': '#991b1b',
      'Chelsea': '#2563eb',
      'Crystal Palace': '#3b82f6',
      'Everton': '#1d4ed8',
      'Fulham': '#64748b',
      'Leeds': '#eab308',
      'Liverpool': '#b91c1c',
      'Man City': '#38bdf8',
      'Man United': '#e11d48',
      'Newcastle': '#f8fafc',
      "Nott'm Forest": '#f43f5e',
      'Sunderland': '#fb923c',
      'Tottenham': '#94a3b8',
      'West Ham': '#be123c',
      'Wolves': '#f59e0b',
    };

    let chartInstance = null;
    let allHistories = {};
    let leaderboardData = [];

    async function loadData() {
      const [sumRes, leadRes, histRes, matchRes] = await Promise.all([
        fetch('/api/summary').then(r => r.json()),
        fetch('/api/leaderboard').then(r => r.json()),
        fetch('/api/history').then(r => r.json()),
        fetch('/api/matches?limit=380').then(r => r.json())
      ]);

      leaderboardData = leadRes.leaderboard;
      allHistories = histRes.histories;

      // Update KPIs
      document.getElementById('kpi-top-team').innerText = sumRes.top_rated.team;
      document.getElementById('kpi-top-rating').innerText = `Rating: ${sumRes.top_rated.rating} (Δ ${sumRes.top_rated.delta_total > 0 ? '+' : ''}${sumRes.top_rated.delta_total})`;

      document.getElementById('kpi-climber-team').innerText = sumRes.biggest_climber.team;
      document.getElementById('kpi-climber-delta').innerText = `Gained +${sumRes.biggest_climber.delta_total} points (#${sumRes.biggest_climber.rank})`;

      document.getElementById('kpi-dropper-team').innerText = sumRes.biggest_dropper.team;
      document.getElementById('kpi-dropper-delta').innerText = `Lost ${sumRes.biggest_dropper.delta_total} points (#${sumRes.biggest_dropper.rank})`;

      document.getElementById('kpi-matches').innerText = sumRes.total_matches;

      // Populate Leaderboard
      const tb = document.getElementById('leaderboard-body');
      tb.innerHTML = leaderboardData.map(row => {
        const deltaClass = row.delta_total >= 0 ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10';
        const sign = row.delta_total >= 0 ? '+' : '';
        const rankBadge = row.rank <= 4 ? 'bg-indigo-500/20 text-indigo-300 font-bold' : (row.rank >= 18 ? 'bg-rose-500/20 text-rose-300' : 'text-gray-400');

        return `
          <tr class="hover:bg-gray-800/40 transition cursor-pointer" onclick="highlightTeam('${row.team}')">
            <td class="py-3 px-3"><span class="px-2 py-0.5 rounded text-xs ${rankBadge}">${row.rank}</span></td>
            <td class="py-3 px-3 font-semibold text-white flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${TEAM_COLORS[row.team] || '#a855f7'}"></span>
              ${row.team}
            </td>
            <td class="py-3 px-3 text-right font-mono font-bold text-gray-100">${row.rating.toFixed(1)}</td>
            <td class="py-3 px-3 text-right font-mono">
              <span class="px-2 py-0.5 rounded text-xs font-semibold ${deltaClass}">${sign}${row.delta_total.toFixed(1)}</span>
            </td>
            <td class="py-3 px-3 text-center text-gray-400">${row.matches_played}</td>
            <td class="py-3 px-3 text-center text-gray-300">${row.goals_for}</td>
            <td class="py-3 px-3 text-center text-gray-400">${row.goals_against}</td>
            <td class="py-3 px-3 text-center font-semibold ${row.goal_difference >= 0 ? 'text-emerald-400' : 'text-rose-400'}">
              ${row.goal_difference > 0 ? '+' : ''}${row.goal_difference}
            </td>
          </tr>
        `;
      }).join('');

      // Top Swings
      const sortedMatches = [...matchRes.matches].sort((a, b) => Math.abs(b.home_delta) - Math.abs(a.home_delta)).slice(0, 8);
      const swingsBox = document.getElementById('swings-container');
      swingsBox.innerHTML = sortedMatches.map(m => {
        const homeWonPoints = m.home_delta > 0;
        return `
          <div class="p-3 rounded-lg bg-gray-900/70 border border-gray-800 text-xs flex flex-col gap-1.5">
            <div class="flex items-center justify-between text-gray-400">
              <span>${m.date.split(' ')[0]}</span>
              <span class="font-mono font-bold ${homeWonPoints ? 'text-emerald-400' : 'text-rose-400'}">
                Δ ${Math.abs(m.home_delta).toFixed(1)} pts
              </span>
            </div>
            <div class="flex items-center justify-between font-medium text-white">
              <span>${m.home_team}</span>
              <span class="font-bold px-2 py-0.5 rounded bg-gray-800 font-mono">${m.ft_score}</span>
              <span>${m.away_team}</span>
            </div>
            <div class="text-[11px] text-gray-500 flex justify-between">
              <span>HT: ${m.ht_score}</span>
              <span>${homeWonPoints ? m.home_team + ' +' + m.home_delta.toFixed(1) : m.away_team + ' +' + Math.abs(m.away_delta).toFixed(1)}</span>
            </div>
          </div>
        `;
      }).join('');

      // Render Trajectory Chart
      renderChart(allHistories);
    }

    function renderChart(histories) {
      const matchdayLabels = Array.from({length: 39}, (_, i) => i === 0 ? 'Start' : `GW ${i}`);
      const datasets = Object.keys(histories).map(team => {
        const teamColor = TEAM_COLORS[team] || '#9333ea';
        return {
          label: team,
          data: histories[team].map(h => h.rating),
          borderColor: teamColor,
          backgroundColor: teamColor,
          borderWidth: 2,
          pointRadius: 1,
          pointHoverRadius: 6,
          tension: 0.25,
          hidden: false
        };
      });

      const ctx = document.getElementById('ratingsChart').getContext('2d');
      chartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels: matchdayLabels,
          datasets: datasets
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: 'nearest',
            axis: 'x',
            intersect: false
          },
          plugins: {
            legend: {
              display: true,
              position: 'bottom',
              labels: {
                boxWidth: 10,
                color: '#9ca3af',
                font: { size: 11 }
              }
            },
            tooltip: {
              backgroundColor: '#111827',
              borderColor: '#374151',
              borderWidth: 1,
              titleColor: '#f3f4f6',
              bodyColor: '#e5e7eb',
              callbacks: {
                label: function(context) {
                  return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}`;
                }
              }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(55, 65, 81, 0.2)' },
              ticks: { color: '#9ca3af', font: { size: 10 } }
            },
            y: {
              grid: { color: 'rgba(55, 65, 81, 0.25)' },
              ticks: { color: '#9ca3af', font: { size: 11 } },
              suggestedMin: 850,
              suggestedMax: 1150
            }
          }
        }
      });
    }

    function filterPresets(type) {
      if (!chartInstance) return;
      const top5Teams = leaderboardData.slice(0, 5).map(x => x.team);
      const bottom5Teams = leaderboardData.slice(-5).map(x => x.team);
      const big6 = ['Arsenal', 'Chelsea', 'Liverpool', 'Man City', 'Man United', 'Tottenham'];

      chartInstance.data.datasets.forEach(ds => {
        if (type === 'all') ds.hidden = false;
        else if (type === 'none') ds.hidden = true;
        else if (type === 'top5') ds.hidden = !top5Teams.includes(ds.label);
        else if (type === 'bottom5') ds.hidden = !bottom5Teams.includes(ds.label);
        else if (type === 'big6') ds.hidden = !big6.includes(ds.label);
      });
      chartInstance.update();
    }

    function highlightTeam(team) {
      if (!chartInstance) return;
      chartInstance.data.datasets.forEach(ds => {
        if (ds.label === team) {
          ds.hidden = false;
          ds.borderWidth = 4;
        } else {
          ds.borderWidth = 1.5;
        }
      });
      chartInstance.update();
      window.scrollTo({ top: 150, behavior: 'smooth' });
    }

    window.addEventListener('DOMContentLoaded', loadData);
  </script>
</body>
</html>
"""


@app.get("/methodology", response_class=HTMLResponse)
def get_methodology():
    """Serves an explanatory page detailing the Goal-Elo system and mathematics."""
    return """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Methodology | WAGD Goal-Elo Ratings</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background-color: #0b0f19; color: #f3f4f6; font-family: system-ui, -apple-system, sans-serif; }
    .glass-card { background: rgba(17, 24, 39, 0.85); backdrop-filter: blur(12px); border: 1px solid rgba(55, 65, 81, 0.5); }
    .code-block { background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(51, 65, 85, 0.6); font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  </style>
</head>
<body class="min-h-screen">
  <!-- Header -->
  <header class="border-b border-gray-800 bg-gray-900/50 backdrop-blur sticky top-0 z-50">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <a href="/" class="w-9 h-9 rounded-lg bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 font-black text-lg hover:scale-105 transition">
          ⚽
        </a>
        <div>
          <a href="/" class="text-lg font-bold tracking-tight text-white flex items-center gap-2 hover:text-emerald-400 transition">
            WAGD <span class="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Methodology</span>
          </a>
          <p class="text-xs text-gray-400">Rating System Architecture & Mathematics</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <a href="/" class="text-xs font-medium text-gray-400 hover:text-white transition px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700">
          ← Dashboard
        </a>
        <a href="/methodology" class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
          Methodology
        </a>
        <a href="/docs" target="_blank" class="text-xs font-medium text-gray-400 hover:text-white transition px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700">
          API Docs
        </a>
      </div>
    </div>
  </header>

  <main class="max-w-4xl mx-auto px-4 sm:px-6 py-10 space-y-10">
    <!-- Hero / Title -->
    <div class="space-y-3">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
        System Overview
      </div>
      <h1 class="text-3xl sm:text-4xl font-black tracking-tight text-white">
        How the Goal-Elo Rating System Works
      </h1>
      <p class="text-gray-400 text-base leading-relaxed">
        WAGD transforms football match outcomes into dynamic, skill-calibrated team ratings using a zero-sum Elo framework adapted for individual goal exchanges.
      </p>
    </div>

    <!-- Section 1: Core Philosophy -->
    <section class="glass-card rounded-2xl p-7 space-y-4">
      <div class="flex items-center gap-3">
        <span class="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 text-indigo-400 font-bold flex items-center justify-center text-sm">1</span>
        <h2 class="text-xl font-bold text-white">The Core Philosophy: Goals as 1v1 Events</h2>
      </div>
      <p class="text-sm text-gray-300 leading-relaxed">
        In standard league standings, a match is reduced to a binary win, draw, or loss (3 points or 1 point). This introduces blind spots:
      </p>
      <ul class="text-sm text-gray-300 space-y-2 list-disc list-inside pl-2">
        <li>A narrow 1–0 victory yields the exact same points as a comprehensive 5–0 masterclass.</li>
        <li>Beating the league champions is rewarded the same as beating a struggling relegation candidate.</li>
        <li>Conceding late goals when ahead carries no standing penalty if the match is still won.</li>
      </ul>
      <p class="text-sm text-gray-300 leading-relaxed">
        <strong>Goal-Elo</strong> re-imagines every goal scored as a distinct contest where the scorer receives a "win" and the conceder receives a "loss", weighted by the relative strength of the two teams at that moment.
      </p>
    </section>

    <!-- Section 2: Mathematical Foundation -->
    <section class="glass-card rounded-2xl p-7 space-y-6">
      <div class="flex items-center gap-3">
        <span class="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 font-bold flex items-center justify-center text-sm">2</span>
        <h2 class="text-xl font-bold text-white">The Mathematical Formulation</h2>
      </div>

      <div class="space-y-3">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-emerald-400">Baseline Starting Rating</h3>
        <p class="text-sm text-gray-300">
          Every club begins Gameweek 0 with a neutral rating of <strong class="text-white font-mono">R₀ = 1000.0</strong>. The total rating pool across all 20 clubs is strictly conserved at <strong class="text-white font-mono">20,000 points</strong>.
        </p>
      </div>

      <div class="space-y-3">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-emerald-400">Expected Goal Probability</h3>
        <p class="text-sm text-gray-300">
          Before a goal is scored, the expected probability $E_A$ of Team A outperforming Team B is derived using the standard logistic distribution curve:
        </p>
        <div class="code-block rounded-xl p-4 text-emerald-300 text-sm overflow-x-auto">
          E_A = 1 / (1 + 10 ^ ((R_B - R_A) / 400))
        </div>
        <p class="text-xs text-gray-400">
          If Team A has a 400-point advantage over Team B, Team A is expected to score with approximately 91% probability on any given goal exchange.
        </p>
      </div>

      <div class="space-y-3">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-emerald-400">Zero-Sum Rating Transfer</h3>
        <p class="text-sm text-gray-300">
          When Team A scores a goal against Team B:
        </p>
        <div class="code-block rounded-xl p-4 space-y-1 text-sm overflow-x-auto text-gray-200">
          <div><span class="text-emerald-400">ΔR</span> = K × (1 - E_A)   <span class="text-gray-500">// where K = 15.0</span></div>
          <div>R_A ← R_A + <span class="text-emerald-400">ΔR</span>       <span class="text-gray-500">// Scorer gains ΔR</span></div>
          <div>R_B ← R_B - <span class="text-emerald-400">ΔR</span>       <span class="text-gray-500">// Conceder loses ΔR</span></div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-2">
          <div class="p-3 rounded-lg bg-gray-900 border border-gray-800">
            <span class="font-bold text-white">Expected Goal (Favorite scores):</span>
            <p class="text-gray-400 mt-1">High $E_A$ (e.g. 0.85) produces a small transfer (Δ ≈ +2.25 pts).</p>
          </div>
          <div class="p-3 rounded-lg bg-gray-900 border border-gray-800">
            <span class="font-bold text-white">Upset Goal (Underdog scores):</span>
            <p class="text-gray-400 mt-1">Low $E_A$ (e.g. 0.15) produces a massive transfer (Δ ≈ +12.75 pts).</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 3: Half-Time Granularity -->
    <section class="glass-card rounded-2xl p-7 space-y-4">
      <div class="flex items-center gap-3">
        <span class="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 font-bold flex items-center justify-center text-sm">3</span>
        <h2 class="text-xl font-bold text-white">Half-Time Temporal Resolution</h2>
      </div>
      <p class="text-sm text-gray-300 leading-relaxed">
        Instead of aggregating all goals at full-time, the engine uses sequential half-time checkpoints:
      </p>
      <div class="space-y-2 text-xs">
        <div class="p-3 rounded-lg bg-gray-900 border border-gray-800 flex items-start gap-3">
          <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">Step 1</span>
          <div>
            <span class="font-semibold text-white">First Half Updates:</span>
            <p class="text-gray-400 mt-0.5">Applies goals from <code class="text-gray-300">HTHG</code> and <code class="text-gray-300">HTAG</code> against pre-match ratings to yield intermediate half-time ratings.</p>
          </div>
        </div>
        <div class="p-3 rounded-lg bg-gray-900 border border-gray-800 flex items-start gap-3">
          <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">Step 2</span>
          <div>
            <span class="font-semibold text-white">Second Half Updates:</span>
            <p class="text-gray-400 mt-0.5">Calculates second half goals <code class="text-gray-300">(FTHG - HTHG)</code> and <code class="text-gray-300">(FTAG - HTAG)</code> and applies them against the intermediate half-time ratings.</p>
          </div>
        </div>
        <div class="p-3 rounded-lg bg-gray-900 border border-gray-800 flex items-start gap-3">
          <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">Step 3</span>
          <div>
            <span class="font-semibold text-white">Gameweek Checkpoint:</span>
            <p class="text-gray-400 mt-0.5">Stores the final post-match rating and records the matchday delta in each team's trajectory curve.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 4: Symmetry & Neutrality -->
    <section class="glass-card rounded-2xl p-7 space-y-4">
      <div class="flex items-center gap-3">
        <span class="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-400 font-bold flex items-center justify-center text-sm">4</span>
        <h2 class="text-xl font-bold text-white">Symmetry & No Artificial Home Bias</h2>
      </div>
      <p class="text-sm text-gray-300 leading-relaxed">
        Because every team in the Premier League plays exactly 19 home games and 19 away games across the 38-game schedule, the system applies <strong>pure neutral rating evaluations</strong> without an artificial home-field constant. This ensures pure symmetry where home and away balance naturally over the course of the full season.
      </p>
    </section>

    <!-- Section 5: Interpretation Guide -->
    <section class="glass-card rounded-2xl p-7 space-y-4">
      <div class="flex items-center gap-3">
        <span class="w-8 h-8 rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-400 font-bold flex items-center justify-center text-sm">5</span>
        <h2 class="text-xl font-bold text-white">Rating Interpretation Guide</h2>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
        <div class="p-3 rounded-xl bg-gray-900 border border-gray-800 space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-emerald-400">&gt; 1100 Rating</span>
            <span class="text-[10px] px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-semibold">Title Contender</span>
          </div>
          <p class="text-gray-400">Elite attack and resolute defense. Consistently converts chances and rarely concedes against mid/lower-tier opposition.</p>
        </div>
        <div class="p-3 rounded-xl bg-gray-900 border border-gray-800 space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-indigo-400">1020 – 1100 Rating</span>
            <span class="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 font-semibold">European Tier</span>
          </div>
          <p class="text-gray-400">Top-six quality. Consistently outperforms the league average with a net positive rating balance.</p>
        </div>
        <div class="p-3 rounded-xl bg-gray-900 border border-gray-800 space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-gray-300">980 – 1020 Rating</span>
            <span class="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-300 font-semibold">Mid-Table</span>
          </div>
          <p class="text-gray-400">Balanced performance around the league median baseline of 1000. Wins and losses largely offset.</p>
        </div>
        <div class="p-3 rounded-xl bg-gray-900 border border-gray-800 space-y-1">
          <div class="flex items-center justify-between">
            <span class="font-bold text-rose-400">&lt; 920 Rating</span>
            <span class="text-[10px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 font-semibold">Relegation Battle</span>
          </div>
          <p class="text-gray-400">Persistent defensive vulnerabilities and heavy point bleed across successive matchdays.</p>
        </div>
      </div>
    </section>

    <!-- Navigation CTA -->
    <div class="text-center pt-4">
      <a href="/" class="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-black font-bold text-sm transition shadow-lg shadow-emerald-500/20">
        ← Back to Live Dashboard
      </a>
    </div>
  </main>

  <footer class="mt-16 border-t border-gray-800 py-6 text-center text-xs text-gray-500">
    WAGD Football Analytics Engine • Built with FastAPI, Chart.js & Tailwind CSS
  </footer>
</body>
</html>
"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)
