import { useEffect, useState, useCallback, useMemo } from 'react'
import './App.css'

const API = 'http://127.0.0.1:8000'
const POSITIONS = ['QB', 'RB', 'WR', 'TE']
const NOTE_BADGE = {
  'Players to Target': { label: 'T', className: 'badge-target', title: 'Target' },
  'Players to Avoid': { label: 'A', className: 'badge-avoid', title: 'Avoid' },
  'Late-Round Dart Throws': { label: 'D', className: 'badge-dart', title: 'Dart Throw' },
}

function NextPicks({ picks }) {
  if (!picks?.length) return null
  return (
    <div className="next-picks">
      <h2>Your Next Picks</h2>
      <div className="next-picks-list">
        {picks.map((p, i) => (
          <span key={i} className="pick-chip">
            R{p.round}{p.overall_pick ? ` · #${p.overall_pick}` : ' · slot TBD'}
          </span>
        ))}
      </div>
    </div>
  )
}

function PositionalSummary({ summary }) {
  if (!summary) return null
  return (
    <div className="positional-summary">
      {POSITIONS.map((pos) => {
        const s = summary[pos]
        if (!s || !s.best_player) return null
        const tierEntries = Object.entries(s.tier_counts).slice(0, 6)
        return (
          <div key={pos} className="pos-card">
            <div className="pos-card-header">{pos}</div>
            <div className="pos-card-best">
              {s.best_player} <span className="tier-tag">T{s.best_tier}</span>
            </div>
            <div className="pos-card-depth">
              {tierEntries.map(([tier, count]) => (
                <span key={tier}>T{tier}: {count}</span>
              ))}
              {Object.keys(s.tier_counts).length > 6 && <span>…</span>}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function NoteModal({ player, onClose }) {
  const [note, setNote] = useState(null)

  useEffect(() => {
    if (!player) return
    fetch(`${API}/note/${encodeURIComponent(player)}`)
      .then((r) => r.json())
      .then((entries) => setNote(entries[0] ?? null))
  }, [player])

  if (!player) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>×</button>
        <h3>{player}</h3>
        {note ? (
          <>
            <p className="modal-meta">{note.section} · Confidence {note.confidence} · Added {note.date_added}</p>
            <p className="modal-note-text">{note.note}</p>
          </>
        ) : (
          <p>Loading…</p>
        )}
      </div>
    </div>
  )
}

function App() {
  const [leagues, setLeagues] = useState([])
  const [selected, setSelected] = useState(null)
  const [data, setData] = useState(null)
  const [pickInput, setPickInput] = useState('')
  const [error, setError] = useState('')
  const [connectionError, setConnectionError] = useState('')
  const [lastUpdated, setLastUpdated] = useState(null)
  const [now, setNow] = useState(Date.now())
  const [positionFilter, setPositionFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [noteModalPlayer, setNoteModalPlayer] = useState(null)

  useEffect(() => {
    fetch(`${API}/leagues`)
      .then((res) => res.json())
      .then((leagues) => {
        setLeagues(leagues)
        setSelected(leagues[0]?.key ?? null)
      })
  }, [])

  const refresh = useCallback(() => {
    if (!selected) return
    fetch(`${API}/best-available/${selected}`)
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json()).detail || `HTTP ${res.status}`)
        return res.json()
      })
      .then((d) => {
        setData(d)
        setLastUpdated(Date.now())
        setConnectionError('')
      })
      .catch((err) => setConnectionError(err.message))
  }, [selected])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 4000)
    return () => clearInterval(interval)
  }, [refresh])

  useEffect(() => {
    const tick = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(tick)
  }, [])

  const markPick = (playerName, by) => {
    setError('')
    return fetch(`${API}/manual-pick/${selected}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player: playerName, by }),
    })
      .then(async (res) => {
        if (!res.ok) throw new Error((await res.json()).detail || 'failed to mark pick')
        refresh()
      })
      .catch((err) => setError(err.message))
  }

  const submitPick = (by) => (e) => {
    e.preventDefault()
    markPick(pickInput, by).then(() => setPickInput(''))
  }

  const unmarkDrafted = (playerName) => {
    fetch(`${API}/manual-pick/${selected}/${encodeURIComponent(playerName)}`, { method: 'DELETE' }).then(refresh)
  }

  const filteredAvailable = useMemo(() => {
    if (!data?.available) return []
    return data.available.filter((p) => {
      if (positionFilter !== 'ALL' && p.position !== positionFilter) return false
      if (search && !p.player.toLowerCase().includes(search.toLowerCase())) return false
      return true
    })
  }, [data, positionFilter, search])

  const secondsAgo = lastUpdated ? Math.round((now - lastUpdated) / 1000) : null

  let prevTier = null
  const upcomingPickQueue = (data?.my_next_picks ?? [])
    .filter((pk) => pk.overall_pick !== null)
    .slice()
    .sort((a, b) => a.overall_pick - b.overall_pick)
  let pickQueueIndex = 0

  return (
    <div className="app">
      <h1>FF Draft Assistant</h1>

      <div className="tabs">
        {leagues.map((l) => (
          <button
            key={l.key}
            className={l.key === selected ? 'tab active' : 'tab'}
            onClick={() => setSelected(l.key)}
          >
            {l.name}
          </button>
        ))}
      </div>

      <div className="status-bar">
        <span>{secondsAgo !== null ? `Updated ${secondsAgo}s ago` : 'Loading...'}</span>
        <button onClick={refresh}>Refresh Now</button>
        {connectionError && <span className="connection-error">⚠ {connectionError} (showing last known data)</span>}
      </div>

      <NextPicks picks={data?.my_next_picks} />
      <PositionalSummary summary={data?.positional_summary} />

      <div className="layout">
        <aside className="sidebar">
          <h2>Drafted ({data?.manual_picks?.length ?? 0})</h2>
          <ul className="drafted-sidebar-list">
            {data?.manual_picks?.map((pick, i) => (
              <li
                key={i}
                className={pick.by === 'me' ? 'mine' : 'theirs'}
                onClick={() => unmarkDrafted(pick.player)}
                title="Click to unmark"
              >
                {pick.by === 'me' && '★ '}{pick.player} <span className="unmark-x">×</span>
              </li>
            ))}
          </ul>
        </aside>

        <div className="main-content">
          <div className="manual-entry">
            <h2>Mark a Pick</h2>
            <form>
              <input
                list="player-names"
                value={pickInput}
                onChange={(e) => setPickInput(e.target.value)}
                placeholder="Player name..."
              />
              <datalist id="player-names">
                {data?.available?.map((p) => (
                  <option key={p.player} value={p.player} />
                ))}
              </datalist>
              <button type="button" onClick={submitPick('me')}>Draft (mine)</button>
              <button type="button" onClick={submitPick('other')}>Picked (other team)</button>
            </form>
            {error && <p className="error">{error}</p>}
          </div>

          {data?.off_the_board?.length > 0 && (
            <div className="off-the-board">
              <h2>Off the board (keepers)</h2>
              <ul>
                {data.off_the_board.map((p) => (
                  <li key={p.player}>
                    {p.player} ({p.position}) — kept, would've cost R{p.keeper_cost_round}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <h2>Best Available ({filteredAvailable.length})</h2>
          <div className="filters">
            {['ALL', ...POSITIONS].map((pos) => (
              <button
                key={pos}
                className={positionFilter === pos ? 'filter-btn active' : 'filter-btn'}
                onClick={() => setPositionFilter(pos)}
              >
                {pos}
              </button>
            ))}
            <input
              className="search-box"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search player..."
            />
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Player</th>
                  <th>Pos</th>
                  <th>Tier</th>
                  <th>ADP</th>
                  <th>Notes</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filteredAvailable.map((p) => {
                  const rows = []
                  if (p.tier !== prevTier) {
                    rows.push(
                      <tr key={`tier-${p.tier}-${p.player}`} className="tier-divider">
                        <td colSpan={7}>Tier {p.tier}</td>
                      </tr>
                    )
                    prevTier = p.tier
                  }
                  while (
                    pickQueueIndex < upcomingPickQueue.length &&
                    p.pick_estimate >= upcomingPickQueue[pickQueueIndex].overall_pick
                  ) {
                    const pk = upcomingPickQueue[pickQueueIndex]
                    rows.push(
                      <tr key={`mypick-${pk.overall_pick}`} className="my-pick-marker">
                        <td colSpan={7}>
                          ↳ Your Pick — Round {pk.round}, #{pk.overall_pick} overall
                        </td>
                      </tr>
                    )
                    pickQueueIndex++
                  }
                  rows.push(
                    <tr key={p.player}>
                      <td>{p.overall_rank}</td>
                      <td>{p.player}</td>
                      <td>{p.position}</td>
                      <td>{p.tier}</td>
                      <td>{p.adp ?? '-'}</td>
                      <td>
                        {p.notes?.map((n) => {
                          const badge = NOTE_BADGE[n.section]
                          if (!badge) return null
                          return (
                            <span
                              key={n.section}
                              className={`badge ${badge.className}`}
                              title={badge.title}
                              onClick={() => setNoteModalPlayer(p.player)}
                            >
                              {badge.label}
                            </span>
                          )
                        })}
                      </td>
                      <td className="row-actions">
                        <button className="draft-btn draft-mine" onClick={() => markPick(p.player, 'me')}>
                          Draft
                        </button>
                        <button className="draft-btn draft-other" onClick={() => markPick(p.player, 'other')}>
                          Picked
                        </button>
                      </td>
                    </tr>
                  )
                  return rows
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <NoteModal player={noteModalPlayer} onClose={() => setNoteModalPlayer(null)} />
    </div>
  )
}

export default App
