"""Browser version of the drill trainer: a large board you click on (or type SAN into).

Same deck, same grading and same Leitner scheduling as drill.py; only the interface differs. It runs a
small local web server (standard library only, localhost) and opens it in your browser.

    uv run python -m chess_improvement.drill              # opens the browser (default)
    uv run python -m chess_improvement.drill --pawn-grabs
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import chess
import chess.engine
import chess.svg
import pandas as pd

from .config import DATA_DIR
from .drills import THREAT, save_deck
from .engine import STOCKFISH

NOTES = DATA_DIR / "drills" / "threat_notes.csv"
COLORS = {"square light": "#f0d9b5", "square dark": "#b58863",
          "square light lastmove": "#cdd26a", "square dark lastmove": "#aaa23a",
          "margin": "#2b2622", "coord": "#e8dcc8"}
SQ, MARGIN = 45, 15  # chess.svg geometry with coordinates=True (viewBox 390 x 390)


def opp_last_move(d: pd.Series) -> chess.Move | None:
    """The opponent's previous move, from the cached per-ply engine table (deck id = '<game>-<ply>')."""
    game, ply = str(d["id"]).rsplit("-", 1)
    f = DATA_DIR / "engine" / "d16" / f"{game}.parquet"
    if not f.exists():
        return None
    p = pd.read_parquet(f, columns=["ply", "played_uci"])
    prev = p.loc[p["ply"] == int(ply) - 1, "played_uci"]
    return chess.Move.from_uci(prev.iloc[0]) if len(prev) else None


def svg(board: chess.Board, orientation: bool, lastmove=None, arrows=()) -> str:
    check = board.king(board.turn) if board.is_check() else None
    return chess.svg.board(board, orientation=orientation, lastmove=lastmove, check=check,
                           arrows=list(arrows), coordinates=True, colors=COLORS, size=None)


class Session:
    def __init__(self, deck: pd.DataFrame, idx: list[int], engine: chess.engine.SimpleEngine):
        self.deck, self.idx, self.engine = deck, idx, engine
        self.k = 0
        self.passed = 0
        self.lock = threading.Lock()

    def current(self) -> dict:
        if self.k >= len(self.idx):
            return {"done": True, "passed": self.passed, "total": len(self.idx)}
        d = self.deck.loc[self.idx[self.k]]
        board = chess.Board(d["fen"])
        last = opp_last_move(d)
        return {
            "done": False, "n": self.k + 1, "total": len(self.idx),
            "side": "White" if board.turn else "Black", "orientation": "white" if board.turn else "black",
            "tc": d["tc"], "move_no": int(d["move_no"]), "wp": float(d["wp_before"]),
            "opp_last": d["opp_last_san"] if isinstance(d["opp_last_san"], str) else None,
            "pawn_grab": bool(d["pawn_grab"]), "fen": d["fen"],
            "svg": svg(board, board.turn, last),
            "legal": {m.uci(): board.san(m) for m in board.legal_moves},
        }

    def answer(self, move_str: str, note: str) -> dict:
        from .drill import grade
        d = self.deck.loc[self.idx[self.k]]
        board = chess.Board(d["fen"])
        move = None
        if move_str:
            try:
                move = chess.Move.from_uci(move_str) if move_str in {m.uci() for m in board.legal_moves} \
                    else board.parse_san(move_str)
            except ValueError:
                return {"error": f"'{move_str}' isn't a legal move here."}
        if move is None:
            ok, mine, best = False, None, None
        else:
            ok, mine, best = grade(board, move, d["best_uci"], self.engine)
        record(self.deck, self.idx[self.k], ok)
        if note.strip():
            write_note(d, note.strip(), board.san(move) if move else "", ok)
        self.passed += ok
        self.k += 1

        best_mv = chess.Move.from_uci(d["best_uci"])
        game_mv = board.parse_san(d["played_san"])
        arrows = [chess.svg.Arrow(game_mv.from_square, game_mv.to_square, color="#d64545cc")]
        if move and move != best_mv:
            arrows.append(chess.svg.Arrow(move.from_square, move.to_square, color="#2a78d6cc"))
        arrows.append(chess.svg.Arrow(best_mv.from_square, best_mv.to_square, color="#2f9e44dd"))
        return {
            "ok": ok, "yours": board.san(move) if move else None,
            "mine": mine, "best": best, "best_san": d["best_san"], "line": d["line"],
            "played_san": d["played_san"], "theme": d["theme"],
            "kind": "you missed their threat" if d["theme"] in THREAT else "you missed a chance",
            "wp_after": float(d["wp_after"]), "url": d["url"],
            "lichess": "https://lichess.org/analysis/" + d["fen"].replace(" ", "_"),
            "svg": svg(board, board.turn, opp_last_move(d), arrows),
        }


def record(deck: pd.DataFrame, i: int, ok: bool) -> None:
    """Leitner update + save (shared with the terminal trainer)."""
    from .drills import BOX_DAYS
    d = deck.loc[i]
    box = min(int(d["box"]) + 1, 5) if ok else 1
    deck.loc[i, ["box", "due"]] = [box, (dt.date.today() + dt.timedelta(days=BOX_DAYS[box])).isoformat()]
    deck.loc[i, "attempts"] = int(d["attempts"]) + 1
    deck.loc[i, "passes"] = int(d["passes"]) + int(ok)
    save_deck(deck)


def write_note(d: pd.Series, note: str, move: str, ok: bool) -> None:
    new = not NOTES.exists()
    with NOTES.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "id", "theme", "my_threat_note", "my_move", "passed", "best", "fen"])
        w.writerow([dt.date.today().isoformat(), d["id"], d["theme"], note, move, ok, d["best_san"], d["fen"]])


def serve(deck: pd.DataFrame, idx: list[int], engine: chess.engine.SimpleEngine, port: int = 8765) -> None:
    sess = Session(deck, idx, engine)
    stop = threading.Event()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the terminal quiet
            pass

        def _send(self, body: str, ctype: str = "application/json") -> None:
            b = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/":
                self._send(PAGE, "text/html")
            elif self.path == "/api/current":
                with sess.lock:
                    self._send(json.dumps(sess.current()))
            else:
                self.send_error(404)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/answer":
                with sess.lock:
                    self._send(json.dumps(sess.answer(body.get("move", ""), body.get("note", ""))))
            elif self.path == "/api/quit":
                self._send("{}")
                stop.set()
            else:
                self.send_error(404)

    httpd = HTTPServer(("127.0.0.1", port), H)
    url = f"http://127.0.0.1:{port}/"
    print(f"Drill board at {url}  (close the tab or press Ctrl+C here to stop; progress saves after every drill)")
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    webbrowser.open(url)
    try:
        stop.wait()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        print(f"Session: {sess.passed}/{sess.k} passed.")


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Chess Drill</title>
<style>
:root{--bg:#f6f4f0;--panel:#fff;--ink:#1d1b18;--muted:#6b655c;--line:#e2ddd4;--accent:#2a78d6;--good:#2f9e44;--bad:#d64545;--warn:#b7791f}
@media (prefers-color-scheme:dark){:root{--bg:#161412;--panel:#221f1b;--ink:#eee8df;--muted:#a39b8f;--line:#38332c;--accent:#5b9cf0;--good:#51c06a;--bad:#ef6b6b;--warn:#e0a63c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{display:flex;gap:28px;padding:20px 24px;max-width:1300px;margin:0 auto;align-items:flex-start;flex-wrap:wrap}
#boardwrap{position:relative;width:min(92vw,calc(100vh - 40px),820px);aspect-ratio:1;flex:none;border-radius:6px;overflow:hidden;box-shadow:0 6px 24px #0003}
#board svg{width:100%;height:100%;display:block;cursor:pointer}
#overlay{position:absolute;inset:0;pointer-events:none}
aside{flex:1;min-width:300px;max-width:440px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin-bottom:14px}
.top{color:var(--muted);font-size:14px;display:flex;justify-content:space-between}
h1{font-size:22px;margin:6px 0 2px}
.last{font-size:30px;font-weight:700;letter-spacing:.5px}
.tag{display:inline-block;font-size:13px;padding:2px 8px;border-radius:99px;background:color-mix(in srgb,var(--warn) 18%,transparent);color:var(--warn);font-weight:600}
label{display:block;font-weight:600;margin-bottom:6px}
textarea,input[type=text]{width:100%;font:inherit;padding:10px 12px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
textarea{min-height:64px;resize:vertical}
button{font:inherit;font-weight:600;padding:10px 16px;border-radius:8px;border:1px solid var(--line);background:var(--panel);color:var(--ink);cursor:pointer}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button:disabled{opacity:.5;cursor:default}
.row{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center}
.hint{color:var(--muted);font-size:14px;margin-top:6px}
.verdict{font-size:26px;font-weight:800}
.ok{color:var(--good)}.bad{color:var(--bad)}
.legend span{display:inline-flex;align-items:center;gap:6px;margin-right:14px;font-size:14px;color:var(--muted)}
.legend i{width:18px;height:4px;border-radius:2px;display:inline-block}
a{color:var(--accent)}
.hidden{display:none}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:14px}
</style></head><body>
<main>
  <div id="boardwrap"><div id="board"></div><svg id="overlay" viewBox="0 0 390 390"></svg></div>
  <aside>
    <div class="card" id="info">
      <div class="top"><span id="count"></span><span id="ctx"></span></div>
      <h1 id="side"></h1>
      <div class="hint">Opponent just played</div>
      <div class="last" id="last"></div>
      <div id="grabtag" class="hidden" style="margin-top:6px"><span class="tag">⚠ pawn-grab position</span></div>
    </div>

    <div class="card" id="step1">
      <label for="note">1 · What is their last move threatening? Checks? Captures?</label>
      <textarea id="note" placeholder="e.g. Qxf7 mate if I move the knight; Bb5 pins my knight…"></textarea>
      <div class="hint">Say it or type it before you look for your move. Anything typed is saved to threat_notes.csv.</div>
      <div class="row"><button class="primary" id="said">I've named the threat →</button></div>
    </div>

    <div class="card hidden" id="step2">
      <label>2 · Your move: click a piece then a square, or type it</label>
      <div class="row"><input type="text" id="san" placeholder="e.g. Nf3, exd5, O-O" autocomplete="off" style="flex:1"></div>
      <div class="row"><span id="pending" class="mono"></span></div>
      <div class="row">
        <button class="primary" id="submit" disabled>Submit</button>
        <button id="undo">Clear</button>
        <button id="skip">I don't know</button>
      </div>
      <div class="hint" id="err"></div>
    </div>

    <div class="card hidden" id="result">
      <div class="verdict" id="verdict"></div>
      <div id="detail" style="margin-top:6px"></div>
      <div class="legend" style="margin-top:10px">
        <span><i style="background:#2f9e44"></i>best</span><span><i style="background:#d64545"></i>you in the game</span><span id="yl"><i style="background:#2a78d6"></i>your answer</span>
      </div>
      <div class="row"><button class="primary" id="next">Next drill →</button></div>
    </div>

    <div class="card hidden" id="done"><h1 id="donemsg"></h1>
      <p>Progress is saved. You can close this tab.</p><div class="row"><button id="quit">Finish</button></div></div>
  </aside>
</main>
<script>
const $=id=>document.getElementById(id);
const SQ=45, M=15;
let cur=null, sel=null, pending=null, enabled=false;
const sqName=(f,r)=>"abcdefgh"[f]+(r+1);
function sqAt(x,y){ // viewBox coords -> square name
  let f=Math.floor((x-M)/SQ), r=7-Math.floor((y-M)/SQ);
  if(f<0||f>7||r<0||r>7) return null;
  if(cur.orientation==="black"){f=7-f;r=7-r;}
  return sqName(f,r);
}
function sqXY(s){let f="abcdefgh".indexOf(s[0]), r=+s[1]-1; if(cur.orientation==="black"){f=7-f;r=7-r;} return [M+f*SQ, M+(7-r)*SQ];}
function drawOverlay(){
  const o=$("overlay"); o.innerHTML="";
  const add=(tag,attrs)=>{const e=document.createElementNS("http://www.w3.org/2000/svg",tag);for(const k in attrs)e.setAttribute(k,attrs[k]);o.appendChild(e);};
  if(pending){ for(const s of [pending.slice(0,2),pending.slice(2,4)]){const [x,y]=sqXY(s); add("rect",{x,y,width:SQ,height:SQ,fill:"#2a78d6",opacity:.45});}}
  else if(sel){
    const [x,y]=sqXY(sel); add("rect",{x,y,width:SQ,height:SQ,fill:"#2a78d6",opacity:.4});
    for(const u in cur.legal) if(u.startsWith(sel)){const [a,b]=sqXY(u.slice(2,4)); add("circle",{cx:a+SQ/2,cy:b+SQ/2,r:7,fill:"#1d1b18",opacity:.35});}
  }
}
function setPending(uci){
  pending=uci; sel=null;
  $("pending").textContent = uci ? "Move: "+cur.legal[uci] : "";
  $("submit").disabled = !uci; $("err").textContent="";
  drawOverlay();
}
$("board").addEventListener("click",ev=>{
  if(!enabled) return;
  const svg=$("board").querySelector("svg"), pt=svg.createSVGPoint(); pt.x=ev.clientX; pt.y=ev.clientY;
  const p=pt.matrixTransform(svg.getScreenCTM().inverse()), s=sqAt(p.x,p.y); if(!s) return;
  if(sel){
    let u=Object.keys(cur.legal).find(k=>k.startsWith(sel+s) && (k.length===4||k[4]==="q"));
    if(u){ $("san").value=""; setPending(u); return; }
  }
  sel = Object.keys(cur.legal).some(k=>k.startsWith(s)) ? s : null; pending=null;
  $("pending").textContent=""; $("submit").disabled=true; drawOverlay();
});
$("san").addEventListener("input",()=>{
  const v=$("san").value.trim().replace(/[+#!?]/g,"");
  const u=Object.keys(cur.legal).find(k=>cur.legal[k].replace(/[+#]/g,"")===v);
  setPending(u||null);
  if(v && !u) $("err").textContent="Not a legal move (yet)…";
});
$("san").addEventListener("keydown",e=>{if(e.key==="Enter"&&pending) submit(pending);});
$("said").onclick=()=>{ $("step2").classList.remove("hidden"); $("said").disabled=true; enabled=true; $("san").focus(); };
$("undo").onclick=()=>{ $("san").value=""; setPending(null); };
$("skip").onclick=()=>submit("");
$("submit").onclick=()=>submit(pending);
$("next").onclick=load;
$("quit").onclick=()=>fetch("/api/quit",{method:"POST"}).then(()=>window.close());

async function submit(move){
  enabled=false; $("submit").disabled=true; $("skip").disabled=true; $("err").textContent="Stockfish is checking…";
  const r=await (await fetch("/api/answer",{method:"POST",body:JSON.stringify({move,note:$("note").value})})).json();
  if(r.error){ $("err").textContent=r.error; enabled=true; $("skip").disabled=false; return; }
  $("board").innerHTML=r.svg; $("overlay").innerHTML="";
  $("step2").classList.add("hidden"); $("result").classList.remove("hidden");
  $("verdict").textContent = r.ok ? "✓ Pass" : (r.yours ? "✗ Not quite" : "✗ Skipped");
  $("verdict").className = "verdict " + (r.ok ? "ok" : "bad");
  $("yl").style.display = (r.yours && r.yours!==r.best_san) ? "" : "none";
  const pct=x=>Math.round(100*x)+"%";
  $("detail").innerHTML =
    (r.yours ? `<p>You chose <b>${r.yours}</b>: keeps ${pct(r.mine)} (best keeps ${pct(r.best)}).</p>` : "") +
    `<p>Best: <b>${r.best_san}</b><br><span class="mono">${r.line}</span></p>` +
    `<p>In the game you played <b>${r.played_san}</b>: ${r.theme}, ${r.kind}; your win chance fell to ${pct(r.wp_after)}.</p>` +
    `<p><a href="${r.lichess}" target="_blank">Explore on lichess</a> · <a href="${r.url}" target="_blank">The game</a></p>`;
  $("next").focus();
}
async function load(){
  cur=await (await fetch("/api/current")).json(); sel=pending=null; enabled=false;
  for(const id of ["result","step2"]) $(id).classList.add("hidden");
  if(cur.done){ for(const id of ["info","step1"]) $(id).classList.add("hidden");
    $("done").classList.remove("hidden"); $("donemsg").textContent=`Session done: ${cur.passed}/${cur.total} passed`; return; }
  $("step1").classList.remove("hidden"); $("said").disabled=false; $("skip").disabled=false;
  $("note").value=""; $("san").value=""; $("pending").textContent=""; $("err").textContent="";
  $("board").innerHTML=cur.svg; drawOverlay();
  $("count").textContent=`Drill ${cur.n} of ${cur.total}`;
  $("ctx").textContent=`${cur.tc} · move ${cur.move_no} · ~${Math.round(100*cur.wp)}% to win`;
  $("side").textContent=`You're ${cur.side} to move`;
  $("last").textContent=cur.opp_last||"—";
  $("grabtag").classList.toggle("hidden",!cur.pawn_grab);
  $("note").focus();
}
load();
</script></body></html>
"""
