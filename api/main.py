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
from scraping_job.csv_extractor import get_available_seasons

app = FastAPI(
    title="WAGD - Premier League Goal-Elo Rating System",
    description="Dynamic football team ratings based on goal-by-goal zero-sum exchanges.",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cached rating results by season
_SEASON_CACHE = {}


def get_cached_ratings(season_id: Optional[str] = None):
    seasons = get_available_seasons()
    selected_season = season_id if season_id else (seasons[0]["id"] if seasons else "2025-2026")
    if selected_season not in _SEASON_CACHE:
        _SEASON_CACHE[selected_season] = get_goal_elo_results(season_id=selected_season)
    return _SEASON_CACHE[selected_season]


@app.get("/api/seasons")
def get_seasons():
    return {"seasons": get_available_seasons()}


@app.get("/api/summary")
def get_summary(season: Optional[str] = None):
    data = get_cached_ratings(season)
    leaderboard = data["leaderboard"]
    top_team = leaderboard[0]
    bottom_team = leaderboard[-1]
    total_goals = sum(row["goals_for"] for row in leaderboard)

    return {
        "season": season or (get_available_seasons()[0]["id"] if get_available_seasons() else "2025-2026"),
        "total_matches": data["total_matches"],
        "base_rating": data["base_rating"],
        "k_factor": data["k_factor"],
        "top_rated": top_team,
        "bottom_rated": bottom_team,
        "total_goals": total_goals,
        "total_teams": len(leaderboard),
    }


@app.get("/api/leaderboard")
def get_leaderboard(season: Optional[str] = None):
    data = get_cached_ratings(season)
    return {"leaderboard": data["leaderboard"]}


@app.get("/api/history")
def get_history(season: Optional[str] = None, team: Optional[str] = None):
    data = get_cached_ratings(season)
    histories = data["team_histories"]
    if team:
        if team not in histories:
            raise HTTPException(status_code=404, detail=f"Team '{team}' not found.")
        return {"team": team, "history": histories[team]}
    return {"histories": histories}


@app.get("/api/matches")
def get_matches(season: Optional[str] = None, limit: int = 50, team: Optional[str] = None):
    data = get_cached_ratings(season)
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
  <title>WAGD | Weight Adjusted Goal Difference</title>
  <script>
    // Suppress playground notice from Tailwind CDN in browser console
    const _warn = console.warn;
    console.warn = function(...args) {
      if (args[0] && typeof args[0] === 'string' && args[0].includes('cdn.tailwindcss.com')) return;
      _warn.apply(console, args);
    };
  </script>
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
        <div>
          <h1 class="text-lg font-bold tracking-tight text-white flex items-center gap-2">
            WAGD <span class="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Weight Adjusted Goal Difference</span>
          </h1>
          <p class="text-xs text-gray-400">Premier League Dynamic Ratings via Quality-Weighted Goal Exchanges</p>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <label for="season-select" class="text-xs text-gray-400 font-medium">Season:</label>
          <select id="season-select" onchange="onSeasonChange()" class="bg-gray-800 hover:bg-gray-700 text-white text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-gray-700 focus:outline-none focus:border-emerald-500 cursor-pointer transition">
          </select>
        </div>
        <div class="h-5 w-px bg-gray-800 hidden sm:block"></div>
        <a href="/" class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
          Dashboard
        </a>
        <a href="/methodology" class="text-xs font-medium text-gray-400 hover:text-white transition px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700">
          Methodology
        </a>
      </div>
    </div>
  </header>

  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
    <!-- KPI Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" id="kpi-container">
      <div class="glass-card rounded-xl p-5 shadow-lg">
        <div class="text-xs font-medium uppercase tracking-wider text-gray-400">#1 Top Rated Team</div>
        <div class="text-2xl font-black mt-1 text-emerald-400" id="kpi-top-team">...</div>
        <div class="text-xs mt-2 text-gray-400 flex items-center gap-1" id="kpi-top-rating">...</div>
      </div>
      <div class="glass-card rounded-xl p-5 shadow-lg">
        <div class="text-xs font-medium uppercase tracking-wider text-gray-400">#20 Lowest Rated Team</div>
        <div class="text-2xl font-black mt-1 text-rose-400" id="kpi-bottom-team">...</div>
        <div class="text-xs mt-2 text-gray-400 flex items-center gap-1" id="kpi-bottom-rating">...</div>
      </div>
      <div class="glass-card rounded-xl p-5 shadow-lg">
        <div class="text-xs font-medium uppercase tracking-wider text-gray-400">Season Goals Scored</div>
        <div class="text-2xl font-black mt-1 text-amber-400" id="kpi-total-goals">...</div>
        <div class="text-xs mt-2 text-gray-400" id="kpi-goals-per-match">...</div>
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
          <div class="flex items-center gap-3">
            <h2 class="text-lg font-bold text-white">Rating Trajectories Across 38 Matchdays</h2>
            <span id="active-filter-indicator" class="hidden text-xs px-2.5 py-1 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-300"></span>
          </div>
          <p class="text-xs text-gray-400">Click any line or table row to isolate a club (click again to restore all)</p>
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
                <th class="py-3 px-3">WAGD</th>
                <th class="py-3 px-3">Team</th>
                <th class="py-3 px-3 text-right">Rating</th>
                <th class="py-3 px-3 text-right">WAGD Δ</th>
                <th class="py-3 px-3 text-center">Table Pos</th>
                <th class="py-3 px-3 text-center">Variance</th>
                <th class="py-3 px-3 text-center">Pts</th>
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
      'Cardiff': '#1d4ed8',
      'Chelsea': '#2563eb',
      'Crystal Palace': '#3b82f6',
      'Everton': '#1e40af',
      'Fulham': '#64748b',
      'Huddersfield': '#38bdf8',
      'Hull': '#d97706',
      'Ipswich': '#2563eb',
      'Leeds': '#eab308',
      'Leicester': '#1d4ed8',
      'Liverpool': '#b91c1c',
      'Luton': '#f97316',
      'Man City': '#38bdf8',
      'Man United': '#e11d48',
      'Middlesbrough': '#dc2626',
      'Newcastle': '#f8fafc',
      'Norwich': '#eab308',
      "Nott'm Forest": '#f43f5e',
      'Sheffield United': '#ef4444',
      'Southampton': '#dc2626',
      'Stoke': '#ef4444',
      'Sunderland': '#fb923c',
      'Swansea': '#f8fafc',
      'Tottenham': '#94a3b8',
      'Watford': '#eab308',
      'West Brom': '#1e3a8a',
      'West Ham': '#be123c',
      'Wolves': '#f59e0b',
    };

    function getTeamColor(team) {
      if (TEAM_COLORS[team]) return TEAM_COLORS[team];
      let hash = 0;
      for (let i = 0; i < team.length; i++) hash = team.charCodeAt(i) + ((hash << 5) - hash);
      const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
      return '#' + '00000'.substring(0, 6 - c.length) + c;
    }

    let chartInstance = null;
    let allHistories = {};
    let leaderboardData = [];
    let currentSeason = '';

    async function loadData(season) {
      const q = season ? `?season=${encodeURIComponent(season)}` : '';
      const [sumRes, leadRes, histRes, matchRes] = await Promise.all([
        fetch('/api/summary' + q).then(r => r.json()),
        fetch('/api/leaderboard' + q).then(r => r.json()),
        fetch('/api/history' + q).then(r => r.json()),
        fetch('/api/matches?limit=380' + (season ? `&season=${encodeURIComponent(season)}` : '')).then(r => r.json())
      ]);

      leaderboardData = leadRes.leaderboard;
      allHistories = histRes.histories;
      currentSeason = sumRes.season;

      // Update KPIs
      document.getElementById('kpi-top-team').innerText = sumRes.top_rated.team;
      document.getElementById('kpi-top-rating').innerText = `Rating: ${sumRes.top_rated.rating} (Δ ${sumRes.top_rated.delta_total > 0 ? '+' : ''}${sumRes.top_rated.delta_total})`;

      document.getElementById('kpi-bottom-team').innerText = sumRes.bottom_rated.team;
      document.getElementById('kpi-bottom-rating').innerText = `Rating: ${sumRes.bottom_rated.rating} (Δ ${sumRes.bottom_rated.delta_total})`;

      document.getElementById('kpi-total-goals').innerText = sumRes.total_goals;
      const goalsPerMatch = (sumRes.total_goals / sumRes.total_matches).toFixed(2);
      document.getElementById('kpi-goals-per-match').innerText = `${goalsPerMatch} goals / match`;

      document.getElementById('kpi-matches').innerText = sumRes.total_matches;

      // Populate Leaderboard
      const tb = document.getElementById('leaderboard-body');
      tb.innerHTML = leaderboardData.map(row => {
        const deltaClass = row.delta_total >= 0 ? 'text-emerald-400 bg-emerald-500/10' : 'text-rose-400 bg-rose-500/10';
        const sign = row.delta_total >= 0 ? '+' : '';
        const rankBadge = row.rank <= 4 ? 'bg-indigo-500/20 text-indigo-300 font-bold' : (row.rank >= 18 ? 'bg-rose-500/20 text-rose-300' : 'text-gray-400');
        
        const rankDiff = row.rank_diff;
        const diffBadge = rankDiff > 0 
          ? `<span class="px-2 py-0.5 rounded text-xs font-bold text-emerald-400 bg-emerald-500/15">+${rankDiff}</span>`
          : (rankDiff < 0 
              ? `<span class="px-2 py-0.5 rounded text-xs font-bold text-rose-400 bg-rose-500/15">${rankDiff}</span>`
              : `<span class="px-2 py-0.5 rounded text-xs text-gray-400 bg-gray-800">=</span>`);

        return `
          <tr data-team="${row.team}" class="hover:bg-gray-800/40 transition cursor-pointer" onclick="isolateTeam('${row.team}')">
            <td class="py-3 px-3"><span class="px-2 py-0.5 rounded text-xs ${rankBadge}">${row.rank}</span></td>
            <td class="py-3 px-3 font-semibold text-white flex items-center gap-2">
              <span class="w-2.5 h-2.5 rounded-full" style="background-color: ${getTeamColor(row.team)}"></span>
              ${row.team}
            </td>
            <td class="py-3 px-3 text-right font-mono font-bold text-gray-100">${row.rating.toFixed(1)}</td>
            <td class="py-3 px-3 text-right font-mono">
              <span class="px-2 py-0.5 rounded text-xs font-semibold ${deltaClass}">${sign}${row.delta_total.toFixed(1)}</span>
            </td>
            <td class="py-3 px-3 text-center font-mono text-gray-300">#${row.official_rank}</td>
            <td class="py-3 px-3 text-center">${diffBadge}</td>
            <td class="py-3 px-3 text-center font-mono font-bold text-gray-200">${row.official_points}</td>
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
      if (chartInstance) {
        chartInstance.destroy();
      }
      const matchdayLabels = Array.from({length: 39}, (_, i) => i === 0 ? 'Start' : `GW ${i}`);
      const sortedTeams = Object.keys(histories).sort();
      const datasets = sortedTeams.map(team => {
        const teamColor = getTeamColor(team);
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
          onClick: (event, elements, chart) => {
            const points = chart.getElementsAtEventForMode(event, 'nearest', { intersect: false }, true);
            if (points && points.length > 0) {
              const datasetIndex = points[0].datasetIndex;
              const team = chart.data.datasets[datasetIndex].label;
              isolateTeam(team);
            }
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

    let isolatedTeam = null;

    function isolateTeam(team) {
      if (!chartInstance) return;
      if (isolatedTeam === team) {
        // Toggle back to showing all
        isolatedTeam = null;
        chartInstance.data.datasets.forEach(ds => {
          ds.hidden = false;
          ds.borderWidth = 2;
        });
        updateFilterBadge(null);
      } else {
        // Isolate this team and filter out all others
        isolatedTeam = team;
        chartInstance.data.datasets.forEach(ds => {
          if (ds.label === team) {
            ds.hidden = false;
            ds.borderWidth = 3.5;
          } else {
            ds.hidden = true;
          }
        });
        updateFilterBadge(team);
      }
      chartInstance.update();
    }

    function updateFilterBadge(team) {
      const badge = document.getElementById('active-filter-indicator');
      if (badge) {
        if (team) {
          badge.innerHTML = `Isolated: <strong class="text-white">${team}</strong> <button onclick="filterPresets('all')" class="ml-1.5 text-xs text-rose-400 hover:text-rose-300 font-bold px-1.5 py-0.5 rounded bg-gray-800 border border-gray-700">Show All ×</button>`;
          badge.classList.remove('hidden');
        } else {
          badge.classList.add('hidden');
        }
      }
      document.querySelectorAll('#leaderboard-body tr').forEach(tr => {
        if (tr.dataset.team === team) {
          tr.classList.add('bg-emerald-500/20');
        } else {
          tr.classList.remove('bg-emerald-500/20');
        }
      });
    }

    function filterPresets(type) {
      if (!chartInstance) return;
      isolatedTeam = null;
      updateFilterBadge(null);
      const top5Teams = leaderboardData.slice(0, 5).map(x => x.team);
      const bottom5Teams = leaderboardData.slice(-5).map(x => x.team);
      const big6 = ['Arsenal', 'Chelsea', 'Liverpool', 'Man City', 'Man United', 'Tottenham'];

      chartInstance.data.datasets.forEach(ds => {
        ds.borderWidth = 2;
        if (type === 'all') ds.hidden = false;
        else if (type === 'none') ds.hidden = true;
        else if (type === 'top5') ds.hidden = !top5Teams.includes(ds.label);
        else if (type === 'bottom5') ds.hidden = !bottom5Teams.includes(ds.label);
        else if (type === 'big6') ds.hidden = !big6.includes(ds.label);
      });
      chartInstance.update();
    }

    async function init() {
      try {
        const res = await fetch('/api/seasons').then(r => r.json());
        const select = document.getElementById('season-select');
        select.innerHTML = res.seasons.map(s => 
          `<option value="${s.id}">${s.label} (${s.id})</option>`
        ).join('');

        currentSeason = res.seasons[0].id;
        select.value = currentSeason;
        await loadData(currentSeason);
      } catch (err) {
        console.error('Failed to initialize seasons:', err);
      }
    }

    async function onSeasonChange() {
      const select = document.getElementById('season-select');
      currentSeason = select.value;
      isolatedTeam = null;
      updateFilterBadge(null);
      await loadData(currentSeason);
    }

    window.addEventListener('DOMContentLoaded', init);
  </script>
</body>
</html>
"""


@app.get("/methodology", response_class=HTMLResponse)
def get_methodology():
    """Serves an explanatory page detailing the Goal-Elo system and mathematics."""
    return r"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Methodology | WAGD - Weight Adjusted Goal Difference</title>
  <script>
    // Suppress playground notice from Tailwind CDN in browser console
    const _warn = console.warn;
    console.warn = function(...args) {
      if (args[0] && typeof args[0] === 'string' && args[0].includes('cdn.tailwindcss.com')) return;
      _warn.apply(console, args);
    };
  </script>
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
        <div>
          <a href="/" class="text-lg font-bold tracking-tight text-white flex items-center gap-2 hover:text-emerald-400 transition">
            WAGD <span class="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">Methodology</span>
          </a>
          <p class="text-xs text-gray-400">Weight Adjusted Goal Difference • Formula & Mechanics</p>
        </div>
      </div>
      <div class="flex items-center gap-3">
        <a href="/" class="text-xs font-medium text-gray-400 hover:text-white transition px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700">
          ← Dashboard
        </a>
        <a href="/methodology" class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
          Methodology
        </a>
      </div>
    </div>
  </header>

  <main class="max-w-4xl mx-auto px-4 sm:px-6 py-10 space-y-10">
    <!-- Hero / Title -->
    <div class="space-y-3">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
        Formula & Specifications
      </div>
      <h1 class="text-3xl sm:text-4xl font-black tracking-tight text-white">
        WAGD Mathematical Formulation
      </h1>
      <p class="text-gray-400 text-base leading-relaxed">
        <strong>WAGD</strong> (Weight Adjusted Goal Difference) models team strength by treating each goal as a zero-sum rating exchange, weighted by the relative rating difference between the two teams at the moment the goal is scored.
      </p>
    </div>

    <!-- Section 1: The Core Formula -->
    <section class="glass-card rounded-2xl p-7 space-y-6">
      <div class="flex items-center gap-3">
        <span class="w-8 h-8 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-400 font-bold flex items-center justify-center text-sm">1</span>
        <h2 class="text-xl font-bold text-white">The Core Elo Equations</h2>
      </div>

      <div class="space-y-3">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-emerald-400">1. Baseline Setup</h3>
        <p class="text-sm text-gray-300">
          Every club begins Gameweek 0 with a base rating of <strong class="text-white font-mono">R₀ = 1000.0</strong>. Across all 20 Premier League clubs, the total league rating pool is strictly fixed:
        </p>
        <div class="code-block rounded-xl p-3 text-emerald-300 text-sm overflow-x-auto">
          Total League Pool = 20 × 1000.0 = 20,000.0 points
        </div>
      </div>

      <div class="space-y-3">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-emerald-400">2. Expected Probability Formula</h3>
        <p class="text-sm text-gray-300">
          For any goal exchange between Team A (rating $R_A$) and Team B (rating $R_B$), the expected probability $E_A$ of Team A scoring relative to Team B is defined by the standard logistic distribution:
        </p>
        <div class="code-block rounded-xl p-4 text-emerald-300 text-sm overflow-x-auto">
          E_A = 1 / (1 + 10 ^ ((R_B - R_A) / 400))
        </div>
        <p class="text-xs text-gray-400">
          Symmetrically, Team B's expected probability is: <code class="text-gray-300">E_B = 1 - E_A = 1 / (1 + 10 ^ ((R_A - R_B) / 400))</code>.
        </p>
      </div>

      <div class="space-y-3">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-emerald-400">3. Zero-Sum Rating Transfer Per Goal</h3>
        <p class="text-sm text-gray-300">
          When Team A scores a goal against Team B:
        </p>
        <div class="code-block rounded-xl p-4 space-y-1.5 text-sm overflow-x-auto text-gray-200">
          <div><span class="text-emerald-400">ΔR</span> = K × (1 - E_A)          <span class="text-gray-500">// K = 15.0</span></div>
          <div>R_A ← R_A + <span class="text-emerald-400">ΔR</span>              <span class="text-gray-500">// Scorer gains ΔR</span></div>
          <div>R_B ← R_B - <span class="text-emerald-400">ΔR</span>              <span class="text-gray-500">// Conceder loses ΔR</span></div>
        </div>
        <p class="text-xs text-gray-400">
          Because Team A gains $+\Delta R$ and Team B loses $-\Delta R$, the net change between the two teams is zero ($\Delta R_A + \Delta R_B = 0$). Points are conserved with zero inflation.
        </p>
      </div>
    </section>

    <!-- Section 2: Numerical Worked Example -->
    <section class="glass-card rounded-2xl p-7 space-y-4">
      <div class="flex items-center gap-3">
        <span class="w-8 h-8 rounded-lg bg-indigo-500/20 border border-indigo-500/40 text-indigo-400 font-bold flex items-center justify-center text-sm">2</span>
        <h2 class="text-xl font-bold text-white">Worked Numerical Example</h2>
      </div>
      <p class="text-sm text-gray-300 leading-relaxed">
        Consider a match between <strong>Team A (Rating: 1100.0)</strong> and <strong>Team B (Rating: 900.0)</strong>:
      </p>
      <div class="code-block rounded-xl p-4 space-y-2 text-xs text-gray-300">
        <div><strong>Rating Difference:</strong> R_B - R_A = 900.0 - 1100.0 = -200.0</div>
        <div><strong>Expected Probability E_A:</strong> 1 / (1 + 10 ^ (-200 / 400)) = 1 / (1 + 10 ^ -0.5) ≈ <strong>0.760 (76.0%)</strong></div>
        <div><strong>Expected Probability E_B:</strong> 1 - 0.760 ≈ <strong>0.240 (24.0%)</strong></div>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs pt-1">
        <div class="p-3.5 rounded-xl bg-gray-900 border border-gray-800 space-y-1.5">
          <div class="font-bold text-white">Scenario 1: Team A Scores</div>
          <div class="font-mono text-emerald-400">ΔR = 15.0 × (1 - 0.760) = +3.60 pts</div>
          <p class="text-gray-400">Team A moves to <strong>1103.60</strong>; Team B moves to <strong>896.40</strong>.</p>
        </div>
        <div class="p-3.5 rounded-xl bg-gray-900 border border-gray-800 space-y-1.5">
          <div class="font-bold text-white">Scenario 2: Team B Scores</div>
          <div class="font-mono text-emerald-400">ΔR = 15.0 × (1 - 0.240) = +11.40 pts</div>
          <p class="text-gray-400">Team B moves to <strong>911.40</strong>; Team A moves to <strong>1088.60</strong>.</p>
        </div>
      </div>
    </section>

    <!-- Section 3: Sequential Half-Time Execution -->
    <section class="glass-card rounded-2xl p-7 space-y-4">
      <div class="flex items-center gap-3">
        <span class="w-8 h-8 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 font-bold flex items-center justify-center text-sm">3</span>
        <h2 class="text-xl font-bold text-white">Sequential Half-Time Processing</h2>
      </div>
      <p class="text-sm text-gray-300 leading-relaxed">
        Matches are evaluated in two chronological stages per fixture:
      </p>
      <div class="space-y-2.5 text-xs">
        <div class="p-3.5 rounded-lg bg-gray-900 border border-gray-800 flex items-start gap-3">
          <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">Stage 1</span>
          <div>
            <span class="font-semibold text-white">First Half Update:</span>
            <p class="text-gray-400 mt-0.5">Goals from <code class="text-gray-300">HTHG</code> and <code class="text-gray-300">HTAG</code> are applied against pre-match ratings, producing intermediate ratings at the 45-minute mark.</p>
          </div>
        </div>
        <div class="p-3.5 rounded-lg bg-gray-900 border border-gray-800 flex items-start gap-3">
          <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">Stage 2</span>
          <div>
            <span class="font-semibold text-white">Second Half Update:</span>
            <p class="text-gray-400 mt-0.5">Second half goals <code class="text-gray-300">(FTHG - HTHG)</code> and <code class="text-gray-300">(FTAG - HTAG)</code> are applied starting from the intermediate half-time ratings.</p>
          </div>
        </div>
        <div class="p-3.5 rounded-lg bg-gray-900 border border-gray-800 flex items-start gap-3">
          <span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold">Stage 3</span>
          <div>
            <span class="font-semibold text-white">Gameweek Checkpoint:</span>
            <p class="text-gray-400 mt-0.5">Post-match ratings are recorded, and the matchday delta is appended to each club's cumulative trajectory curve.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 4: Symmetry & Fixture Neutrality -->
    <section class="glass-card rounded-2xl p-7 space-y-4">
      <div class="flex items-center gap-3">
        <span class="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-400 font-bold flex items-center justify-center text-sm">4</span>
        <h2 class="text-xl font-bold text-white">Symmetry & Parameter Specifications</h2>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
        <div class="p-4 rounded-xl bg-gray-900 border border-gray-800 space-y-1">
          <div class="font-bold text-white text-sm">K-Factor ($K = 15.0$)</div>
          <p class="text-gray-400">Controls the maximum possible rating exchange per goal event. Calibrated to allow meaningful movement per match without extreme variance.</p>
        </div>
        <div class="p-4 rounded-xl bg-gray-900 border border-gray-800 space-y-1">
          <div class="font-bold text-white text-sm">Fixture Symmetry</div>
          <p class="text-gray-400">Calculations treat home and away teams neutrally without an artificial offset constant, matching the balanced 19 home and 19 away schedule.</p>
        </div>
      </div>
    </section>

    <!-- Navigation CTA -->
    <div class="text-center pt-4">
      <a href="/" class="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-emerald-500 hover:bg-emerald-600 text-black font-bold text-sm transition shadow-lg shadow-emerald-500/20">
        &larr; Back to Live Dashboard
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
