import chess
import chess.engine
import chess.pgn
import re
import sys
import time
import argparse
import csv
import os

# --- CUSTOM LOGGER FOR FILE OUTPUT ---
class TeeLogger:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log_file = open(filename, "w", encoding="utf-8", errors="ignore")
        # Regex to catch all ANSI color and formatting codes
        self.ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def write(self, message):
        self.terminal.write(message) 
        if not self.log_file.closed:
            clean_message = self.ansi_escape.sub('', message)
            self.log_file.write(clean_message)
            self.log_file.flush()  # <--- NEW: Forces the OS to write to disk instantly
            os.fsync(self.log_file.fileno()) # <--- NEW: Guarantees macOS updates the file size immediately

    def flush(self):
        self.terminal.flush()
        if not self.log_file.closed:
            self.log_file.flush()

    def close(self):
        if not self.log_file.closed:
            self.log_file.close()
        sys.stdout = self.terminal

# --- CSV TELEMETRY EXPORTER ---
class CSVLogger:
    def __init__(self, filename):
        self.filename = filename
        self.headers = [
            "Date", "Ply", "Move_Number", "Color", "Player_Name", "Move_Played", 
            "Clock_Seconds", "Eval", "Win_Prob", "Expected_WP", "Awareness_WP", 
            "KSI", "Fragility", "Forgiveness", "Desperation", "Intuitiveness", 
            "Time_Pressure", "Dread_Factor", "Vertigo_Multiplier", 
            "Best_SF_Move", "Best_Maia_Move", "Top_Chaos_Move"
        ]
        with open(self.filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)

    def log_turn(self, date, ply, move_num, color, player, move_played, clock_ms, m):
        if not m: return 
        
        with open(self.filename, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            best_sf = m["moves_data"][m["sf_moves"][0]]["san"] if m["sf_moves"] else ""
            best_maia = m["moves_data"][m["maia_moves"][0]]["san"] if m["maia_moves"] else ""
            top_chaos = m["moves_data"][m["chaos_moves"][0]]["san"] if m["chaos_moves"] else ""

            row = [
                date, ply, move_num, color, player, move_played, 
                round(clock_ms / 1000.0, 1), 
                m["eval"], round(m["wp"], 2), round(m["exp_wp"], 2), round(m["awareness"], 2),
                round(m["ksi"], 2), round(m["frag"], 2), round(m["forg"], 2), 
                round(m["dsp"], 2), round(m["int"], 2), round(m["tp"], 2),
                round(m["dread_factor"], 3), round(m["vertigo_mult"], 3),
                best_sf, best_maia, top_chaos
            ]
            writer.writerow(row)

# --- COLOR & UI HELPERS ---
def format_clock(ms):
    total_seconds = max(0, ms // 1000)
    m, s = divmod(total_seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{int(h)}:{int(m):02d}:{int(s):02d}"
    return f"{int(m):02d}:{int(s):02d}"

def get_heat_color(val, reverse=False):
    val = max(0.0, min(100.0, float(val)))
    if reverse: val = 100.0 - val
    if val <= 50:
        pct = val / 50.0
        r, g, b = int(100 + (155 * pct)), int(150 + (105 * pct)), int(255 - (255 * pct))
    else:
        pct = (val - 50.0) / 50.0
        r, g, b = 255, int(255 - (205 * pct)), 0
    return f"\033[38;2;{r};{g};{b}m"

RESET = "\033[0m"

def get_marker(val, reverse=False):
    val = max(0.0, min(100.0, float(val)))
    if reverse: val = 100.0 - val
    if val < 40: return "🟦"
    if val < 65: return "🟨"
    if val < 85: return "🟧"
    return "🟥"

def get_ratio_marker(ratio):
    if ratio == float('inf') or ratio >= 3.0: return "🟩"
    if ratio >= 1.0: return "🟨"
    if ratio >= 0.1: return "🟧"
    return "🟥"

def colorize(val, text=None, reverse=False):
    display_text = text if text is not None else f"{val:.1f}"
    return f"{get_heat_color(val, reverse)}{display_text}{RESET}"

def format_modifier(val, is_weight=False, is_vertigo=False):
    if abs(val) < 0.1: return ""
    sym = "💫" if is_vertigo else "😰"
    if is_weight:
        return f"({val:+.0f}% {sym})"
    return f"({val:+.1f} {sym})"

# --- MAIN ENGINE ---
class ChessThermometer:
    def __init__(self, sf_path, lc0_path, weights_path, threads, tc_mode="auto", fast_mode=False, csv_path=None):
        print(f"[*] Loading Engines (Maia: {weights_path})...")
        try:
            self.sf = chess.engine.SimpleEngine.popen_uci(sf_path)
            self.sf.configure({"Threads": threads, "Hash": 1024}) 
            self.maia = chess.engine.SimpleEngine.popen_uci(lc0_path)
            self.maia.configure({"WeightsFile": weights_path})
        except Exception as e:
            print(f"[!] Engine Error: {e}")
            sys.exit(1)
        
        self.board = chess.Board()
        self.history = {chess.WHITE: None, chess.BLACK: None}
        self.clocks = {chess.WHITE: None, chess.BLACK: None}
        self.starting_clocks = {chess.WHITE: None, chess.BLACK: None}
        self.player_elos = {chess.WHITE: 2800, chess.BLACK: 2800}
        self.tc_mode = tc_mode
        self.fast_mode = fast_mode
        
        self.csv_logger = CSVLogger(csv_path) if csv_path else None
        if self.csv_logger:
            print(f"[*] CSV Telemetry enabled. Logging to {csv_path}")

    def close(self):
        print("\n[*] Shutting down engines cleanly...")
        try:
            self.sf.quit()
            self.maia.quit()
        except Exception:
            pass

    def parse_elo(self, elo_str, default=2800):
        try:
            return int(elo_str)
        except (ValueError, TypeError):
            return default

    def get_default_clock(self):
        if self.tc_mode == "classical":
            return 7200000  # 120 minutes
        elif self.tc_mode == "rapid":
            return 900000   # 15 minutes
        elif self.tc_mode == "blitz":
            return 180000   # 3 minutes
        return 600000       # 10 minutes (auto)

    def parse_clk(self, comment, current_turn):
        # The (?:(\d+):)? makes the "Hours:" portion optional
        match = re.search(r'\[%clk (?:(\d+):)?(\d+):(\d+(?:\.\d+)?)\]', comment)
        if match:
            # If hours are missing, default to 0
            h = float(match.group(1)) if match.group(1) else 0.0
            m = float(match.group(2))
            s = float(match.group(3))
            return int((h * 3600 + m * 60 + s) * 1000)
            
        # FIX: If the clock tag is missing, fall back to the player's last known clock.
        if self.clocks[current_turn] is not None:
            return self.clocks[current_turn]
            
        return self.get_default_clock()

    def score_to_cp(self, score_obj):
        if score_obj.is_mate():
            return 10.0 if score_obj.mate() > 0 else -10.0
        return score_obj.score() / 100.0

    def format_score(self, score_obj):
        if score_obj.is_mate(): return f"#{score_obj.mate()}"
        return f"{score_obj.score() / 100.0:+.2f}"

    def get_wp(self, score_pov):
        return score_pov.wdl(model="sf").expectation() * 100

    def get_quick_sf_eval(self, move, turn, depth=10, time_limit=0.5):
        quick_info = self.sf.analyse(self.board, chess.engine.Limit(time=time_limit), root_moves=[move])
        if quick_info and "score" in quick_info:
            score = quick_info["score"].pov(turn)
            return self.format_score(score), self.get_wp(score), self.score_to_cp(score)
        return "+0.00", 50.0, 0.0

    def analyze_position(self, time_ms, opp_time_ms, opp_last_ksi, is_chaos_sim=False):
        if self.board.is_game_over(): return None

        turn = self.board.turn
        legal_count = self.board.legal_moves.count()
        if legal_count == 0: return None
        
        # --- DYNAMIC ENGINE LIMITS & CIRCUIT BREAKERS ---
        sf_depth = 10 if is_chaos_sim else 18
        sf_time = 0.5 if is_chaos_sim else 2.0  # Max 2 seconds per main search
        sf_multipv = min(legal_count, 5 if is_chaos_sim else 10)
        
        maia_nodes = 10
        maia_multipv = min(legal_count, 5 if is_chaos_sim else 10)
        
        quick_depth = 6 if is_chaos_sim else 10
        quick_time = 0.2 if is_chaos_sim else 0.5 # Max 0.5 seconds for fallbacks
        # ------------------------------------------------

        moves_data = {} 

        # 1. ENGINE TRUTH
        sf_info = self.sf.analyse(self.board, chess.engine.Limit(time=sf_time), multipv=sf_multipv)
        sf_top_moves = []
        absolute_eval = "+0.00"
        
        for i, info in enumerate(sf_info):
            if "pv" not in info: continue
            move = info["pv"][0]
            score_pov = info["score"].pov(turn)
            
            if i == 0:
                absolute_eval = self.format_score(info["score"].white())

            moves_data[move] = {
                "san": self.board.san(move),
                "sf_cp_str": self.format_score(score_pov),
                "cp_float": self.score_to_cp(score_pov),
                "sf_wp": self.get_wp(score_pov),
                "human_prob": 0.0, 
                "chaos_delta": 0.0,
                "risk": 0.0, "reward": 0.0, "ratio": 0.0
            }
            sf_top_moves.append(move)

        if not sf_top_moves: return None
        best_wp = moves_data[sf_top_moves[0]]["sf_wp"]
        best_cp = moves_data[sf_top_moves[0]]["cp_float"]

        # 2. DESPERATION (Activates at 40% WP)
        raw_dsp = max(0.0, (40.0 - best_wp) * 2.5) 
        desperation = ((raw_dsp / 100.0) ** 0.5) * 100.0

        # 3. RAW FRAGILITY & FORGIVENESS (Blended WP/CP)
        raw_fragility_drop = 0.0
        dread_ratio = desperation / 100.0 # The crossfader
        
        for i in range(len(sf_top_moves) - 1):
            wp_drop = max(0, moves_data[sf_top_moves[i]]["sf_wp"] - moves_data[sf_top_moves[i+1]]["sf_wp"])
            
            # CP Fragility (1.0 pawn drop = ~15% WP drop equivalent)
            cp_drop = max(0, moves_data[sf_top_moves[i]]["cp_float"] - moves_data[sf_top_moves[i+1]]["cp_float"])
            equiv_wp_drop = cp_drop * 15.0 
            
            # Crossfade: Winning = WP Drop. Losing = CP Drop.
            blended_drop = (wp_drop * (1.0 - dread_ratio)) + (equiv_wp_drop * dread_ratio)
            
            weight = 0.5 ** (i + 1)
            raw_fragility_drop += blended_drop * weight
        
        base_fragility = ((raw_fragility_drop * 2.0) / 100.0) ** 0.75 * 100 if raw_fragility_drop > 0 else 0.0

        if len(sf_top_moves) > 1:
            forgiving_moves = sum(1 for m in sf_top_moves if moves_data[m]["sf_wp"] >= best_wp - 5.0)
            raw_ratio = (forgiving_moves - 1) / (len(sf_top_moves) - 1)
            forgiveness = (raw_ratio ** 0.5) * 100 * min(1.0, best_wp / 50.0)
        else:
            forgiveness = 0.0

        # 4. HUMAN INTUITION & EXPECTED WP
        maia_info = self.maia.analyse(self.board, chess.engine.Limit(nodes=maia_nodes), multipv=maia_multipv)
        maia_top_moves = []
        
        raw_weights = [1.0 / (2 ** i) for i in range(len(maia_info))]
        total_weight = sum(raw_weights) if sum(raw_weights) > 0 else 1.0
        
        # --- BATCH EVALUATE MISSING MAIA MOVES ---
        # Instead of calling SF individually, we batch them into one fast call
        missing_moves = []
        for info in maia_info:
            if "pv" in info:
                move = info["pv"][0]
                if move not in moves_data:
                    missing_moves.append(move)
                    
        if missing_moves:
            infos = self.sf.analyse(self.board, chess.engine.Limit(time=quick_time), root_moves=missing_moves, multipv=len(missing_moves))
            if isinstance(infos, dict): infos = [infos] # Safety catch for single-move returns
            for info in infos:
                if "pv" not in info: continue
                m = info["pv"][0]
                score_pov = info["score"].pov(turn)
                moves_data[m] = {
                    "san": self.board.san(m),
                    "sf_cp_str": self.format_score(score_pov),
                    "cp_float": self.score_to_cp(score_pov),
                    "sf_wp": self.get_wp(score_pov),
                    "human_prob": 0.0, 
                    "chaos_delta": 0.0,
                    "risk": 0.0, "reward": 0.0, "ratio": 0.0
                }
        # -----------------------------------------

        expected_wp = 0.0
        expected_cp = 0.0

        for i, info in enumerate(maia_info):
            if "pv" not in info: continue
            move = info["pv"][0]
            prob = raw_weights[i] / total_weight
            
            if move in moves_data:
                moves_data[move]["human_prob"] = prob * 100
                expected_wp += prob * moves_data[move]["sf_wp"]
                expected_cp += prob * moves_data[move]["cp_float"]
                
            maia_top_moves.append(move)

        base_intuitiveness = max(0, 100 - (best_wp - expected_wp))

        # 5. AWARENESS & VERTIGO
        int_factor = base_intuitiveness / 100.0
        
        current_elo = self.player_elos[turn]
        raw_vision = (current_elo - 2200) / 1400.0
        base_gm_vision = max(0.0, min(1.0, raw_vision))
        
        gm_vision = base_gm_vision + ((1.0 - base_gm_vision) * int_factor)
        awareness_wp = (gm_vision * best_wp) + ((1.0 - gm_vision) * expected_wp)

        # Vertigo activates at 90% WP
        vertigo_mult = 1.0
        if awareness_wp > 90.0:
            vertigo_mult = 1.0 + ((awareness_wp - 90.0) / 10.0)

        fragility = min(100.0, base_fragility * vertigo_mult)
        intuitiveness = max(0.0, 100.0 - ((100.0 - base_intuitiveness) * vertigo_mult))

        # 6. TIME PRESSURE
        time_sec = max(1, time_ms) / 1000.0
        opp_time_sec = max(1, opp_time_ms) / 1000.0
        move_num = self.board.fullmove_number
        
        base_tp = 0.0
        if is_chaos_sim:
            base_tp = 0.0 # Disabled during chaos simulation
        elif self.tc_mode == "classical":
            if move_num <= 40:
                moves_remaining = 41 - move_num
                sec_per_move = time_sec / moves_remaining
                if sec_per_move <= 15:
                    base_tp = 100.0
                elif sec_per_move < 90:
                    base_tp = ((90 - sec_per_move) / 75.0) * 100.0
            else:
                if time_sec <= 30:
                    base_tp = 100.0
                elif time_sec < 300:
                    base_tp = ((300 - time_sec) / 270.0) * 100.0
        else:
            # Auto / Rapid / Blitz (Uses 15% of starting clock)
            start_ms = self.starting_clocks[turn]
            if start_ms is None: start_ms = self.get_default_clock() 
            start_sec = start_ms / 1000.0
            threshold = start_sec * 0.15
            min_time = threshold * 0.1 

            if time_sec <= min_time:
                base_tp = 100.0
            elif time_sec < threshold:
                base_tp = ((threshold - time_sec) / (threshold - min_time)) * 100.0

        # Disparity Multiplier
        time_pressure = base_tp
        if base_tp > 0 and opp_time_sec > 0:
            ratio = opp_time_sec / time_sec
            if ratio > 1.25:
                capped_ratio = min(4.0, ratio)
                mult = 1.0 + ((capped_ratio - 1.25) / 2.75) * 0.5
                time_pressure = min(100.0, base_tp * mult)

        # 7. KSI (The Elo-Shield)
        dread_factor = desperation / 100.0
        
        # Intuitiveness Resilience shatters as panic sets in
        int_resilience = base_gm_vision * (1.0 - dread_factor)
        int_drain_pct = dread_factor * (1.0 - int_resilience)
        
        # Fragility Resilience is stubborn; it holds steady based on GM Elo
        frag_resilience = base_gm_vision
        frag_drain_pct = dread_factor * (1.0 - frag_resilience)
        
        # Drain the weights
        w_frag = 0.25 * (1.0 - frag_drain_pct)
        w_int  = 0.20 * (1.0 - int_drain_pct)
        
        # Pour drained weights into Desperation
        drained_frag = 0.25 * frag_drain_pct
        drained_int  = 0.20 * int_drain_pct
        w_dsp  = 0.25 + drained_frag + drained_int
        
        w_forg = 0.20 
        w_tp   = 0.10 

        ksi = (w_frag * fragility) + (w_forg * (100 - forgiveness)) + (w_int * (100 - intuitiveness)) + (w_dsp * desperation) + (w_tp * time_pressure)

        if is_chaos_sim:
            return {"ksi": ksi, "best_cp": best_cp, "expected_cp": expected_cp}

        # 8. CHAOS DELTAS (Bypassed if --fast is enabled)
        display_chaos = []
        display_sf = sf_top_moves[:5]
        display_maia = sorted(maia_top_moves, key=lambda m: moves_data[m]["human_prob"], reverse=True)[:5]
        
        if not self.fast_mode:
            unique_display_moves = set(display_sf + display_maia)
            for move in unique_display_moves:
                risk = max(0.0, best_cp - moves_data[move]["cp_float"])
                moves_data[move]["risk"] = risk

                self.board.push(move)
                sim_data = self.analyze_position(self.get_default_clock(), self.get_default_clock(), opp_last_ksi, is_chaos_sim=True)
                self.board.pop()
                
                if sim_data:
                    moves_data[move]["chaos_delta"] = sim_data["ksi"] - opp_last_ksi
                    reward = max(0.0, sim_data["best_cp"] - sim_data["expected_cp"])
                    moves_data[move]["reward"] = reward
                    
                    if risk < 0.01:
                        moves_data[move]["ratio"] = float('inf')
                    else:
                        moves_data[move]["ratio"] = reward / risk

            display_chaos = sorted(list(unique_display_moves), key=lambda m: moves_data[m]["chaos_delta"], reverse=True)[:5]

        return {
            "eval": absolute_eval, "wp": best_wp, "exp_wp": expected_wp, "awareness": awareness_wp, "gm_vision": gm_vision,
            "base_gm_vision": base_gm_vision, # <--- ADD THIS LINE
            "ksi": ksi, "frag": fragility, "forg": forgiveness, "int": intuitiveness, "dsp": desperation, "tp": time_pressure,
            "base_frag": base_fragility, "base_int": base_intuitiveness,
            "vertigo_mult": vertigo_mult, "dread_factor": dread_factor,
            "weights": {"frag": w_frag, "forg": w_forg, "int": w_int, "dsp": w_dsp, "tp": w_tp},
            "sf_moves": display_sf, "maia_moves": display_maia, "chaos_moves": display_chaos,
            "moves_data": moves_data
        }

    def format_delta(self, current, previous):
        if previous is None: return "(N/A)"
        delta = current - previous
        return f"({delta:+.1f})"

    def print_ui(self, m, prev, time_ms):
        w = m["weights"]
        
        v_frag_boost = m['frag'] - m['base_frag']
        v_int_boost = m['int'] - m['base_int'] 
        
        d_frag_drain = (w['frag'] - 0.25) * 100
        d_int_drain = (w['int'] - 0.20) * 100
        d_dsp_boost = (w['dsp'] - 0.25) * 100

        clock_str = format_clock(time_ms)

        wp_blend_pct = (1.0 - m['dread_factor']) * 100
        cp_blend_pct = m['dread_factor'] * 100

        print(f"📊 TRUTH (Stockfish): {m['eval']} [WP: {m['wp']:.1f}%] | HUMAN (Maia): Exp WP: {m['exp_wp']:.1f}% | PERCEIVED: {m['awareness']:.1f}% [Blend: {m['gm_vision']*100:.0f}% SF / {(1.0-m['gm_vision'])*100:.0f}% Maia]")
        print(f"⚙️ MODIFIERS: Dread: {m['dread_factor']:.2f} | Vertigo: {m['vertigo_mult']:.2f}x | Obj. Res: {m['base_gm_vision']*100:.0f}% | Frag Blend: {wp_blend_pct:.0f}% WP / {cp_blend_pct:.0f}% CP | ⏱️ Clock: {clock_str}\n")

        print(f"{get_marker(m['ksi'])} KSI: {colorize(m['ksi'], f'{m['ksi']:.1f}')} {self.format_delta(m['ksi'], prev['ksi'] if prev else None)} "
              f"| {get_marker(m['frag'])} Frag: {colorize(m['frag'])} {self.format_delta(m['frag'], prev['frag'] if prev else None)} {format_modifier(v_frag_boost, False, True)} [W:{w['frag']*100:.0f}% {format_modifier(d_frag_drain, True, False)}] "
              f"| {get_marker(m['forg'], reverse=True)} Forg: {colorize(m['forg'], reverse=True)} {self.format_delta(m['forg'], prev['forg'] if prev else None)} [W:{w['forg']*100:.0f}%] "
              f"| {get_marker(m['int'], reverse=True)} Int: {colorize(m['int'], reverse=True)} {self.format_delta(m['int'], prev['int'] if prev else None)} {format_modifier(v_int_boost, False, True)} [W:{w['int']*100:.0f}% {format_modifier(d_int_drain, True, False)}] "
              f"| {get_marker(m['dsp'])} Dsp: {colorize(m['dsp'])} {self.format_delta(m['dsp'], prev['dsp'] if prev else None)} [W:{w['dsp']*100:.0f}% {format_modifier(d_dsp_boost, True, False)}] "
              f"| {get_marker(m['tp'])} TP: {colorize(m['tp'])} {self.format_delta(m['tp'], prev['tp'] if prev else None)} [W:{w['tp']*100:.0f}%]")
        
        md = m["moves_data"]
        best_wp = md[m["sf_moves"][0]]["sf_wp"]
        best_cp = md[m["sf_moves"][0]]["cp_float"]

        print(f"\n💻 TOP 5 ENGINE TRUTH (Stockfish):")
        for i, move in enumerate(m["sf_moves"], 1):
            d = md[move]
            drop_off_cp = max(0.0, best_cp - d["cp_float"])
            drop_off_wp = max(0.0, best_wp - d["sf_wp"])
            heat = min(100.0, drop_off_cp * 50.0)
            marker = get_marker(heat)
            c_sf = colorize(heat, f"{d['sf_cp_str']:>5} SF")
            print(f"  {i}. {d['san']:<6} | {marker} {c_sf} [{-drop_off_wp:5.1f}% WP] | {d['human_prob']:>2.0f}% Human Prob")

        print(f"\n🧍 TOP 5 HUMAN INSTINCT (Maia):")
        for i, move in enumerate(m["maia_moves"], 1):
            d = md[move]
            drop_off_cp = max(0.0, best_cp - d["cp_float"])
            drop_off_wp = max(0.0, best_wp - d["sf_wp"])
            heat = min(100.0, drop_off_cp * 50.0)
            marker = get_marker(heat)
            c_sf = colorize(heat, f"{d['sf_cp_str']:>5} SF")
            print(f"  {i}. {d['san']:<6} | {d['human_prob']:>2.0f}% Human Prob | {marker} {c_sf} [{-drop_off_wp:5.1f}% WP]")

        if m["chaos_moves"]:
            print(f"\n🔥 TOP 5 CHAOS MOVES:")
            for i, move in enumerate(m["chaos_moves"], 1):
                d = md[move]
                ratio_str = "∞" if d['ratio'] == float('inf') else f"{d['ratio']:.1f}"
                c_ksi = colorize(max(0, min(100, 50 + d['chaos_delta'])), f"{d['chaos_delta']:+.1f}")
                print(f"  {i}. {d['san']:<6} ({c_ksi}) | Risk: {d['risk']:.2f} | Rwd: {d['reward']:.2f} | Ratio: {ratio_str:<3} ({get_ratio_marker(d['ratio'])})")
        print("")

    def print_played_move(self, m, move, move_san, player_name, time_ms, current_turn):
        prev_clock = self.clocks[current_turn]
        if prev_clock is None:
            prev_clock = self.get_default_clock()
            
        time_taken = "N/A"
        if prev_clock is not None:
            secs = max(0, int((prev_clock - time_ms) / 1000))
            m_time, s_time = divmod(secs, 60)
            time_taken = f"{m_time}m {s_time}s" if m_time > 0 else f"{s_time}s"
            
        if m and "moves_data" in m:
            md = m["moves_data"]
            if move in md:
                d = md[move]
                cp = d["sf_cp_str"]
                wp = d["sf_wp"]
                hp = d["human_prob"]
                risk = d["risk"]
                rwd = d["reward"]
                ratio = d["ratio"]
                chaos = d["chaos_delta"]
            else:
                cp, wp, cp_float = self.get_quick_sf_eval(move, current_turn)
                hp = 0.0
                best_cp = md[m["sf_moves"][0]]["cp_float"]
                risk = max(0.0, best_cp - cp_float)
                
                if not self.fast_mode:
                    self.board.push(move)
                    sim_data = self.analyze_position(self.get_default_clock(), self.get_default_clock(), 0.0, is_chaos_sim=True)
                    self.board.pop()
                    
                    if sim_data:
                        opp_last_ksi = self.history[not current_turn]["ksi"] if self.history[not current_turn] else 0.0
                        chaos = sim_data["ksi"] - opp_last_ksi
                        rwd = max(0.0, sim_data["best_cp"] - sim_data["expected_cp"])
                        ratio = float('inf') if risk < 0.01 else rwd / risk
                    else:
                        chaos = 0.0
                        rwd = 0.0
                        ratio = 0.0
                else:
                    chaos = 0.0
                    rwd = 0.0
                    ratio = 0.0
            
            if self.fast_mode:
                stats_str = f" | Eval: {cp} (WP: {wp:.1f}%) | Human: {hp:.0f}%"
            else:
                ratio_str = "∞" if ratio == float('inf') else f"{ratio:.1f}"
                c_chaos = colorize(max(0, min(100, 50 + chaos)), f"{chaos:+.1f}")
                stats_str = f" | Eval: {cp} (WP: {wp:.1f}%) | Human: {hp:.0f}% | Chaos: {c_chaos} | Risk: {risk:.2f} | Rwd: {rwd:.2f} | Ratio: {ratio_str}"
        else:
            stats_str = ""
            
        print(f"🎯 [{time_taken}] {player_name} played: {move_san}{stats_str}")

    def analyze_full_game(self, pgn_path):
        print(f"[*] Loading full game from {pgn_path}...")
        try:
            with open(pgn_path) as pgn_file:
                game = chess.pgn.read_game(pgn_file)
            if not game: return

            white_name = game.headers.get('White', 'White')
            black_name = game.headers.get('Black', 'Black')
            
            self.player_elos[chess.WHITE] = self.parse_elo(game.headers.get('WhiteElo'))
            self.player_elos[chess.BLACK] = self.parse_elo(game.headers.get('BlackElo'))
            
            raw_date = game.headers.get('Date', '????.??.??')
            raw_time = game.headers.get('UTCTime', game.headers.get('Time', ''))
            game_date = f"{raw_date} {raw_time}".strip()
            print(f"\n[*] MATCH: {white_name} vs {black_name} ({game_date})")
            
            node = game
            while node.variations:
                next_node = node.variation(0)
                move = next_node.move

                current_turn = self.board.turn
                time_ms = self.parse_clk(next_node.comment, current_turn)
                
                opp_color = not current_turn
                player_name = white_name if current_turn == chess.WHITE else black_name
                color_str = "White" if current_turn == chess.WHITE else "Black"
                
                if self.starting_clocks[current_turn] is None:
                    self.starting_clocks[current_turn] = time_ms

                eval_time = self.clocks[current_turn] if self.clocks[current_turn] else self.get_default_clock()
                opp_time_ms = self.clocks[opp_color] if self.clocks[opp_color] else self.get_default_clock()
                
                move_num = self.board.fullmove_number
                move_str = f"{move_num}." if current_turn == chess.WHITE else f"{move_num}..."
                
                print(f"\n========================================================")
                print(f"⏳ POSITION: [{move_str}] {player_name} ({color_str}) to play")
                print(f"========================================================")

                opp_last_ksi = self.history[opp_color]["ksi"] if self.history[opp_color] else 0.0
                m = self.analyze_position(eval_time, opp_time_ms, opp_last_ksi)
                
                if m:
                    prev = self.history[current_turn]
                    self.print_ui(m, prev, eval_time)
                    self.history[current_turn] = m
                
                move_san = self.board.san(move)
                
                self.print_played_move(m, move, move_san, player_name, time_ms, current_turn)
                
                if self.csv_logger and m:
                    self.csv_logger.log_turn(
                        date=game_date,
                        ply=self.board.ply() + 1,
                        move_num=move_num,
                        color=color_str,
                        player=player_name,
                        move_played=move_san,
                        clock_ms=eval_time,
                        m=m
                    )

                self.board.push(move)
                self.clocks[current_turn] = time_ms
                node = next_node
        except Exception as e:
            print(f"[!] Error analyzing game: {e}")

    def watch_live_pgn(self, pgn_path, poll_interval=5, fast_forward=True):
        print(f"[*] Watching {pgn_path} for live updates...")
        processed_ply = 0
        live_metrics_calculated = False

        while True:
            try:
                with open(pgn_path) as pgn_file:
                    game = chess.pgn.read_game(pgn_file)
                if not game:
                    time.sleep(poll_interval)
                    continue

                raw_date = game.headers.get('Date', '????.??.??')
                raw_time = game.headers.get('UTCTime', game.headers.get('Time', ''))
                game_date = f"{raw_date} {raw_time}".strip()
                
                self.player_elos[chess.WHITE] = self.parse_elo(game.headers.get('WhiteElo'))
                self.player_elos[chess.BLACK] = self.parse_elo(game.headers.get('BlackElo'))
                
                node = game
                moves_in_pgn = []
                while node.variations:
                    next_node = node.variation(0)
                    moves_in_pgn.append(next_node)
                    node = next_node

                if len(moves_in_pgn) > processed_ply:
                    for i in range(processed_ply, len(moves_in_pgn)):
                        new_node = moves_in_pgn[i]
                        move = new_node.move
                        
                        current_turn = self.board.turn # <-- MOVED UP
                        time_ms = self.parse_clk(new_node.comment, current_turn) # <-- UPDATED
                        
                        opp_color = not current_turn

                        if self.starting_clocks[current_turn] is None:
                            self.starting_clocks[current_turn] = time_ms

                        eval_time = self.clocks[current_turn] if self.clocks[current_turn] else self.get_default_clock()
                        opp_time_ms = self.clocks[opp_color] if self.clocks[opp_color] else self.get_default_clock()
                        
                        is_historical = fast_forward and ((len(moves_in_pgn) - i) > 2)
                        
                        if not live_metrics_calculated:
                            if is_historical:
                                self.history[current_turn] = {"ksi": 0.0, "dsp": 0.0, "frag": 0.0, "forg": 0.0, "int": 0.0, "tp": 0.0}
                                m = None 
                            else:
                                opp_last_ksi = self.history[opp_color]["ksi"] if self.history[opp_color] else 0.0
                                m = self.analyze_position(eval_time, opp_time_ms, opp_last_ksi)
                                self.history[current_turn] = m
                        else:
                            m = self.history[current_turn]
                        
                        turn_name = game.headers.get('White') if current_turn == chess.WHITE else game.headers.get('Black')
                        color_str = "White" if current_turn == chess.WHITE else "Black"
                        
                        if is_historical:
                            print(f"\r⏩ Fast-forwarding to live edge... ({i}/{len(moves_in_pgn)})", end="")
                        else:
                            if i == len(moves_in_pgn) - 2 and fast_forward: print("") 
                            
                            if not fast_forward and m and not live_metrics_calculated:
                                move_num = self.board.fullmove_number
                                move_str = f"{move_num}." if current_turn == chess.WHITE else f"{move_num}..."
                                print(f"\n========================================================")
                                print(f"⏳ HISTORICAL POSITION: [{move_str}] {turn_name} to play")
                                print(f"========================================================")
                                self.print_ui(m, self.history.get(current_turn), eval_time)

                            move_san = self.board.san(move)
                            self.print_played_move(m, move, move_san, turn_name, time_ms, current_turn)
                            
                            if self.csv_logger and m:
                                self.csv_logger.log_turn(
                                    date=game_date,
                                    ply=self.board.ply() + 1,
                                    move_num=self.board.fullmove_number,
                                    color=color_str,
                                    player=turn_name,
                                    move_played=move_san,
                                    clock_ms=eval_time,
                                    m=m
                                )
                        
                        self.board.push(move)
                        self.clocks[current_turn] = time_ms
                        processed_ply += 1

                        live_metrics_calculated = False
                    
                    live_metrics_calculated = False

                if len(moves_in_pgn) == processed_ply and not live_metrics_calculated:
                    current_turn = self.board.turn
                    opp_color = not current_turn
                    player_name = game.headers.get('White') if current_turn == chess.WHITE else game.headers.get('Black')
                    color_str = "White" if current_turn == chess.WHITE else "Black"
                    
                    eval_time = self.clocks[current_turn] if self.clocks[current_turn] else self.get_default_clock()
                    opp_time_ms = self.clocks[opp_color] if self.clocks[opp_color] else self.get_default_clock()
                    move_num = self.board.fullmove_number
                    move_str = f"{move_num}." if current_turn == chess.WHITE else f"{move_num}..."
                    
                    print(f"\n========================================================")
                    print(f"⏳ LIVE POSITION: [{move_str}] {player_name} ({color_str}) is thinking...")
                    print(f"========================================================")
                    
                    opp_last_ksi = self.history[opp_color]["ksi"] if self.history[opp_color] else 0.0
                    m = self.analyze_position(eval_time, opp_time_ms, opp_last_ksi)
                    
                    if m:
                        prev = self.history[current_turn]
                        self.print_ui(m, prev, eval_time)
                        self.history[current_turn] = m
                        
                        if self.csv_logger:
                            self.csv_logger.log_turn(
                                date=game_date,
                                ply=self.board.ply() + 1,
                                move_num=move_num,
                                color=color_str,
                                player=player_name,
                                move_played="Thinking...",
                                clock_ms=eval_time,
                                m=m
                            )
                    
                    live_metrics_calculated = True

            except Exception as e:
                pass
                
            time.sleep(poll_interval)

# ==========================================
# CLI ENTRY POINT
# ==========================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kirsch Stress Index Evaluator - Chess Player Psychological Stress Evaluation Tool")
    parser.add_argument("--mode", choices=["live", "full"], default="live", help="Run mode: 'live' tailing or 'full' game batch analysis.")
    parser.add_argument("--tc", choices=["auto", "classical", "rapid", "blitz"], default="auto", help="Time control mode for calculating Time Pressure.")
    parser.add_argument("--fast", action="store_true", help="Skip Chaos Move simulations for much faster processing (highly recommended for full game reviews).")
    parser.add_argument("--pgn", default="chess.pgn", help="Path to the PGN file.")
    parser.add_argument("--csv", default="chess.csv", help="Path to the output CSV file.")
    parser.add_argument("--sf", default=r"engines\stockfish\stockfish-windows-x86-64-avx2.exe", help="Path to Stockfish executable.")
    parser.add_argument("--lc0", default=r"engines\lc0\lc0.exe", help="Path to Lc0 executable.")
    parser.add_argument("--weights", default=r"engines\lc0\maia-2200.pb.gz", help="Path to Maia weights.")
    parser.add_argument("--no-ff", action="store_true", help="Disable fast-forwarding in live mode.")
    parser.add_argument("--output", help="Save the output to a text file.")
    parser.add_argument("--threads", type=int, default=8, help="Number of CPU threads for Stockfish.")
    parser.add_argument("--poll", type=int, default=5, help="Live mode polling interval in seconds.")
    
    args = parser.parse_args()

    logger = None
    if args.output:
        logger = TeeLogger(args.output)
        sys.stdout = logger
        print(f"[*] Logging output to {args.output}")

    tracker = ChessThermometer(
        sf_path=args.sf, 
        lc0_path=args.lc0, 
        weights_path=args.weights, 
        threads=args.threads,
        tc_mode=args.tc,
        fast_mode=args.fast,
        csv_path=args.csv
    )
    
    try:
        if args.mode == "live":
            tracker.watch_live_pgn(args.pgn, poll_interval=args.poll, fast_forward=not args.no_ff)
        else:
            tracker.analyze_full_game(args.pgn)
    except KeyboardInterrupt:
        print("\n[*] Process interrupted by user.")
    finally:
        tracker.close()
        if logger:
            logger.close()