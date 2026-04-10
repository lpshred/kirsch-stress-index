import pandas as pd
import argparse
import math
import os

# =============================================================================
# 1. THE TWEAK ZONE (Global Settings)
# =============================================================================

# The Climax Settings
PEAK_WINDOW_SIZE = 3
PRESSURE_COOKER_WINDOW = 3
BLUNDER_WP_DROP_THRESHOLD = 15.0 

# The Final Collapse Settings
COLLAPSE_CP_DROP_THRESHOLD = 3.0 
COLLAPSE_MAX_STARTING_WP = 10.0  

# The Tightrope Walk Settings 
TIGHTROPE_FORGIVENESS_THRESHOLD = 20.0 
TIGHTROPE_MIN_LENGTH = 3
TIGHTROPE_MIN_RATIO = 0.8 
TIGHTROPE_MIN_WP = 10.0  
TIGHTROPE_MAX_WP = 90.0  

# The Chaos Trap Settings
CHAOS_WP_DROP_REWARD = 15.0

# The Extremes Settings
VERTIGO_MIN_WP = 75.0
VERTIGO_MIN_MULT = 1.5
CRUCIBLE_MIN_TP = 40.0
IRON_MIND_MIN_DESPERATION = 40.0 
IRON_MIND_MIN_IMPROVEMENT = 0.5 

# The Nuance Blocks Settings
UNPUNISHED_WP_DROP = 15.0
BURDEN_WINDOW_MOVES = 5 
BURDEN_MAX_EVAL = 1.5 

# Shared Perception Thresholds
MIN_MUTUAL_OPTIMISM = 115.0
MAX_MUTUAL_PESSIMISM = 85.0

# Deep Tank Thresholds
DEEP_TANK_MIN_MINUTES = 5.0
ALL_IN_TIME_PERCENTAGE = 40.0

# =============================================================================
# 2. HELPER FUNCTIONS
# =============================================================================

def format_clock(seconds):
    if pd.isna(seconds) or seconds < 0: return "00:00:00"
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    
    if h > 0:
        return f"{h}h {m}m {s}s"
    elif m > 0:
        return f"{m}m {s}s"
    else:
        return f"{s}s"

def parse_eval(e_str):
    if pd.isna(e_str): return 0.0
    e_str = str(e_str).strip()
    if '#' in e_str:
        val = float(e_str.replace('#', ''))
        return -20.0 if val < 0 else 20.0 
    return float(e_str)

# =============================================================================
# 3. DATA INGESTION (Forward-Looking Math & Data Scrubbing)
# =============================================================================

def load_data(file_path):
    try:
        df = pd.read_csv(file_path)
        df = df[df['Move_Played'] != 'Thinking...'].copy()
        
        df['Ply'] = pd.to_numeric(df['Ply'], errors='coerce')
        df = df.dropna(subset=['Ply']) 
        df = df.sort_values(by="Ply").reset_index(drop=True)
        
        # --- CLOCK BUG FIX ---
        start_time = df['Clock_Seconds'].max()
        df['Bad_Clock'] = (df['Clock_Seconds'] == start_time) & (df['Ply'] > 2)
        df.loc[df['Bad_Clock'], 'Clock_Seconds'] = pd.NA
        df['Clock_Seconds'] = df.groupby('Player_Name')['Clock_Seconds'].ffill()
        
        # Time calculations
        df['Prev_Clock'] = df.groupby('Player_Name')['Clock_Seconds'].shift(1)
        df['Time_Spent_Sec'] = df['Prev_Clock'] - df['Clock_Seconds']
        df['Time_Spent_Sec'] = df['Time_Spent_Sec'].fillna(0).clip(lower=0)
        df['Time_Spent_Min'] = df['Time_Spent_Sec'] / 60.0
        
        # --- ZERO-SECOND POLLING DELAY FIX ---
        df['Prev_Bad_Clock'] = df.groupby('Player_Name')['Bad_Clock'].shift(1).fillna(False)
        df['Zero_Sec_Move'] = df['Time_Spent_Sec'] == 0.0
        df['Prev_Zero_Sec'] = df.groupby('Player_Name')['Zero_Sec_Move'].shift(1).fillna(False)
        
        # A think time is ONLY valid if the current clock, prev clock, and prev think time were all good
        df['Valid_Think_Time'] = (~df['Bad_Clock']) & (~df['Prev_Bad_Clock']) & (~df['Prev_Zero_Sec'])
        
        # Relative Time Spent
        df['Time_Spent_Pct'] = (df['Time_Spent_Sec'] / df['Prev_Clock']) * 100.0
        df['Time_Spent_Pct'] = df['Time_Spent_Pct'].fillna(0.0).clip(upper=100.0)
        
        # Peek at NEXT ply
        df['Next_Ply_Eval'] = df['Eval'].shift(-1)
        df['Next_Ply_WP'] = df['Win_Prob'].shift(-1)
        
        df['Eval_Num'] = df['Eval'].apply(parse_eval)
        df['Next_Ply_Eval_Num'] = df['Eval_Num'].shift(-1).fillna(df['Eval_Num'])
        
        # FORWARD-LOOKING DROPS
        df['WP_Drop'] = df['Win_Prob'] - (100.0 - df['Next_Ply_WP'].fillna(100.0 - df['Win_Prob']))
        
        df['CP_Loss'] = 0.0
        white_mask = df['Color'] == 'White'
        black_mask = df['Color'] == 'Black'
        df.loc[white_mask, 'CP_Loss'] = df['Eval_Num'] - df['Next_Ply_Eval_Num']
        df.loc[black_mask, 'CP_Loss'] = df['Next_Ply_Eval_Num'] - df['Eval_Num']
        
        return df
    except Exception as e:
        print(f"❌ Error reading the CSV: {e}")
        return None

# =============================================================================
# 4. NARRATIVE METRICS (The LEGO Blocks)
# =============================================================================

def get_tale_of_the_tape(df):
    stats_list = []
    for player in df['Player_Name'].unique():
        player_df = df[df['Player_Name'] == player]
        color = player_df['Color'].iloc[0]
        stats_list.append({
            'Player_Name': player, 'Color': color,
            'min': round(player_df['KSI'].min(), 1),
            'max': round(player_df['KSI'].max(), 1),
            'mean': round(player_df['KSI'].mean(), 1),
            'total_ksi': round(player_df['KSI'].sum(), 1),
            'total_mins': round(player_df['Time_Spent_Min'].sum(), 1),
            'ksi_per_min': round(player_df['KSI'].sum() / player_df['Time_Spent_Min'].sum() if player_df['Time_Spent_Min'].sum() > 0 else 0.0, 1)
        })
    return pd.DataFrame(stats_list)

def get_climax(df):
    if df['WP_Drop'].isna().all() or df['WP_Drop'].max() < BLUNDER_WP_DROP_THRESHOLD:
        window_size = int(PEAK_WINDOW_SIZE)
        
        df['Is_Repetition'] = (df.groupby('Player_Name')['Move_Played'].shift(1) == df['Move_Played']) | \
                              (df.groupby('Player_Name')['Move_Played'].shift(2) == df['Move_Played'])
        
        df['Rolling_KSI'] = df.groupby('Player_Name')['KSI'].transform(lambda x: x.rolling(window=window_size, min_periods=1).sum())
        df['Penalized_Rolling_KSI'] = df.apply(lambda row: 0.0 if row['Is_Repetition'] else row['Rolling_KSI'], axis=1)
        
        peak_end_row = df.loc[df['Penalized_Rolling_KSI'].idxmax()]
        target_player = peak_end_row['Player_Name']
        player_df = df[df['Player_Name'] == target_player]
        window_df = player_df[player_df['Ply'] <= peak_end_row['Ply']].tail(window_size)
        return False, target_player, window_df
    else:
        biggest_drop_idx = df['WP_Drop'].idxmax()
        blunder_row = df.loc[biggest_drop_idx]
        target_player = blunder_row['Player_Name']
        player_df = df[df['Player_Name'] == target_player]
        
        cooker_window = int(PRESSURE_COOKER_WINDOW) + 1
        cooker_moves = player_df[player_df['Ply'] <= blunder_row['Ply']].tail(cooker_window)
        return True, blunder_row, cooker_moves

def get_final_collapse(df, climax_blunder_row):
    collapses = df[(df['Win_Prob'] <= COLLAPSE_MAX_STARTING_WP) & 
                   (df['CP_Loss'] >= COLLAPSE_CP_DROP_THRESHOLD)].copy()
                   
    if climax_blunder_row is not None and not collapses.empty:
        collapses = collapses[collapses['Ply'] != climax_blunder_row['Ply']]
        
    if collapses.empty: return None
    return collapses.loc[collapses['CP_Loss'].idxmax()]

def get_deep_tank(df):
    tank_rows = df[(df['Time_Spent_Min'] >= DEEP_TANK_MIN_MINUTES) & df['Valid_Think_Time']].copy()
    if tank_rows.empty: return None
    
    top_thinks = {}
    for player in tank_rows['Player_Name'].unique():
        player_df = tank_rows[tank_rows['Player_Name'] == player]
        top_3 = player_df.sort_values(by='Time_Spent_Sec', ascending=False).head(3)
        top_thinks[player] = top_3
        
    return top_thinks

def get_deepest_fog(df):
    return df.loc[df['Intuitiveness'].idxmin()]

def get_tightrope_walk(df):
    df['Is_Fragile'] = (df['Forgiveness'] <= TIGHTROPE_FORGIVENESS_THRESHOLD) & \
                       (df['Win_Prob'] >= TIGHTROPE_MIN_WP) & \
                       (df['Win_Prob'] <= TIGHTROPE_MAX_WP)
                       
    best_player, best_window_df = None, None
    max_len = 0
    
    for player in df['Player_Name'].unique():
        p_df = df[df['Player_Name'] == player].reset_index(drop=True)
        if len(p_df) < TIGHTROPE_MIN_LENGTH: continue
        
        p_df['Cons_3'] = p_df['Is_Fragile'].rolling(3).sum() == 3
        p_df['Double_Safe'] = (~p_df['Is_Fragile']) & (~p_df['Is_Fragile']).shift(1)
        
        player_best_len = 0
        player_best_window = None
        
        for w in range(len(p_df), TIGHTROPE_MIN_LENGTH - 1, -1):
            req_fragile = math.ceil(TIGHTROPE_MIN_RATIO * w)
            rolling_counts = p_df['Is_Fragile'].rolling(w).sum()
            rolling_double_safe = p_df['Double_Safe'].rolling(w).sum()
            
            for end_idx in range(w - 1, len(p_df)):
                if rolling_counts.iloc[end_idx] >= req_fragile and rolling_double_safe.iloc[end_idx] == 0:
                    start_idx = end_idx - w + 1
                    if p_df['Cons_3'].iloc[start_idx+2 : end_idx+1].any():
                        player_best_len = w
                        player_best_window = p_df.iloc[start_idx : end_idx + 1]
                        break
            if player_best_len > 0:
                break
        
        if player_best_len > max_len:
            max_len = player_best_len
            best_player = player
            fragile_indices = player_best_window[player_best_window['Is_Fragile']].index
            if not fragile_indices.empty:
                best_window_df = player_best_window.loc[fragile_indices[0] : fragile_indices[-1]]
            
    return best_player, best_window_df

def get_chaos_traps(df):
    df['Next_Ply_WP_Drop'] = df['WP_Drop'].shift(-1)
    
    successful = df[(df['Move_Played'] == df['Top_Chaos_Move']) & 
                    (df['Move_Played'] != df['Best_SF_Move']) & 
                    (df['WP_Drop'] < BLUNDER_WP_DROP_THRESHOLD) & 
                    (df['Next_Ply_WP_Drop'] >= CHAOS_WP_DROP_REWARD)]
                    
    successful_trap = successful.loc[successful['Next_Ply_WP_Drop'].idxmax()] if not successful.empty else None
    
    return successful_trap

def get_vertigo_spike(df):
    vertigo_rows = df[(df['Win_Prob'] >= VERTIGO_MIN_WP) & (df['Vertigo_Multiplier'] >= VERTIGO_MIN_MULT)].copy()
    if vertigo_rows.empty: return None
    vertigo_rows['Vertigo_Score'] = vertigo_rows['KSI'] * vertigo_rows['Vertigo_Multiplier']
    return df.loc[vertigo_rows['Vertigo_Score'].idxmax()]

def get_crucible(df):
    if df['Time_Pressure'].max() < CRUCIBLE_MIN_TP: return None, None
    peak_tp_idx = df['Time_Pressure'].idxmax()
    peak_row = df.loc[peak_tp_idx]
    target_player = peak_row['Player_Name']
    player_df = df[df['Player_Name'] == target_player]
    crucible_moves = player_df[player_df['Ply'] <= peak_row['Ply']].tail(4)
    return target_player, crucible_moves

def get_iron_mind(df):
    df['Is_Doomed'] = df['Desperation'] >= IRON_MIND_MIN_DESPERATION
    df['Is_Best_Move'] = df['Move_Played'] == df['Best_SF_Move']
    df['Iron_Condition'] = df['Is_Doomed'] & df['Is_Best_Move']
    
    best_player, best_streak_len, best_streak_df = None, 0, None
    
    for player in df['Player_Name'].unique():
        p_df = df[df['Player_Name'] == player].reset_index(drop=True)
        p_df['Streak_Group'] = (~p_df['Iron_Condition']).cumsum()
        
        valid_moves = p_df[p_df['Iron_Condition']]
        streaks = valid_moves.groupby('Streak_Group').size()
        
        if not streaks.empty:
            max_len = streaks.max()
            if max_len > best_streak_len:
                best_streak_len = max_len
                best_player = player
                best_group = streaks.idxmax()
                best_streak_df = valid_moves[valid_moves['Streak_Group'] == best_group]
                
    if best_streak_len >= 2:
        return best_player, best_streak_len, best_streak_df
    return None, 0, None

def get_unpunished_blunder(df):
    double_blunders = df[(df['WP_Drop'] >= UNPUNISHED_WP_DROP) & 
                         (df['WP_Drop'].shift(-1) >= UNPUNISHED_WP_DROP)].copy()
    if double_blunders.empty: return None, None
    
    blunder_A_idx = double_blunders['WP_Drop'].idxmax()
    blunder_A = df.loc[blunder_A_idx]
    blunder_B = df.loc[blunder_A_idx + 1]
    
    return blunder_A, blunder_B

def get_burden_of_precision(df):
    plies_needed = BURDEN_WINDOW_MOVES * 2
    if len(df) < plies_needed: return None, None, None, None
    
    df['Is_Balanced'] = df['Eval_Num'].abs() <= BURDEN_MAX_EVAL
    
    best_start_idx = -1
    max_delta = 0.0
    
    for i in range(len(df) - plies_needed + 1):
        window = df.iloc[i : i + plies_needed]
        
        if not window['Is_Balanced'].all():
            continue
            
        white_avg = window[window['Color'] == 'White']['Forgiveness'].mean()
        black_avg = window[window['Color'] == 'Black']['Forgiveness'].mean()
        delta = abs(white_avg - black_avg)
        
        if delta > max_delta:
            max_delta = delta
            best_start_idx = i
            
    if best_start_idx == -1:
        return None, None, None, None
        
    best_window = df.iloc[best_start_idx : best_start_idx + plies_needed]
    white_avg = best_window[best_window['Color'] == 'White']['Forgiveness'].mean()
    black_avg = best_window[best_window['Color'] == 'Black']['Forgiveness'].mean()
    
    white_player = best_window[best_window['Color'] == 'White']['Player_Name'].iloc[0]
    black_player = best_window[best_window['Color'] == 'Black']['Player_Name'].iloc[0]
    
    if white_avg > black_avg:
        return best_window, white_player, white_avg, black_player, black_avg 
    else:
        return best_window, black_player, black_avg, white_player, white_avg 

def get_shared_perception(df):
    grouped = df.groupby('Move_Number')
    valid_moves = grouped.filter(lambda x: len(x) == 2)
    
    if valid_moves.empty: return None, None
    
    summed_awareness = valid_moves.groupby('Move_Number')['Awareness_WP'].sum().reset_index()
    summed_awareness.columns = ['Move_Number', 'Combined_Awareness']
    
    peak_opt_move = summed_awareness.loc[summed_awareness['Combined_Awareness'].idxmax()]
    peak_pess_move = summed_awareness.loc[summed_awareness['Combined_Awareness'].idxmin()]
    
    opt_rows = valid_moves[valid_moves['Move_Number'] == peak_opt_move['Move_Number']]
    pess_rows = valid_moves[valid_moves['Move_Number'] == peak_pess_move['Move_Number']]
    
    final_opt = opt_rows if peak_opt_move['Combined_Awareness'] >= MIN_MUTUAL_OPTIMISM else None
    final_pess = pess_rows if peak_pess_move['Combined_Awareness'] <= MAX_MUTUAL_PESSIMISM else None
    
    return final_opt, final_pess

# =============================================================================
# 5. THE STORY WEAVER (Markdown Generation - Introspective Tone)
# =============================================================================

def generate_markdown(df, tape_stats, climax_data, collapse_row, tank_data, fog_row, tightrope_data, successful_trap, vertigo_row, crucible_data, iron_mind_data, unpunished_data, burden_data, perception_data, input_filepath, out_filepath=None):
    white_player = df[df['Color'] == 'White']['Player_Name'].iloc[0]
    black_player = df[df['Color'] == 'Black']['Player_Name'].iloc[0]
    
    # Handle output routing for Phase 3 wrapper
    if out_filepath:
        filename = out_filepath
    else:
        base_dir = os.path.dirname(input_filepath)
        if not base_dir:
            base_dir = "."
        base_name = os.path.splitext(os.path.basename(input_filepath))[0]
        filename = os.path.join(base_dir, f"{base_name}_storyboard.md")
    
    md = f"# KSI Match Storyboard: {white_player} (W) vs {black_player} (B)\n\n"
    
    # 1. TALE OF THE TAPE
    md += "## 📊 The Tale of the Tape\n"
    md += "*A comparative look at the psychological demands placed on both players.*\n\n"
    for index, row in tape_stats.iterrows():
        md += f"**{row['Player_Name']} ({row['Color']})**\n"
        md += f"- **Total Match Stress:** {row['total_ksi']} KSI *(Over {row['total_mins']} mins of thought)*\n"
        md += f"- **Pacing:** {row['mean']} KSI / move | {row['ksi_per_min']} KSI / minute\n"
        md += f"- **Extremes:** Peaked at {row['max']} KSI, dipped to {row['min']} KSI\n\n"
        
    # 2. THE CLIMAX
    is_blunder, climax_obj1, climax_obj2 = climax_data
    
    if is_blunder:
        blunder_row = climax_obj1
        cooker_moves = climax_obj2
        md += "---\n## 📉 The Turning Point\n"
        md += f"*The critical moment where the objective evaluation shifted most drastically.*\n\n"
        
        start_eval = blunder_row['Eval']
        next_eval = blunder_row['Next_Ply_Eval'] if not pd.isna(blunder_row['Next_Ply_Eval']) else "Game Over"
        
        md += f"The most significant shift occurred on **Move {blunder_row['Move_Number']}**. **{blunder_row['Player_Name']}** played **{blunder_row['Move_Played']}**, moving the objective evaluation from {start_eval} to {next_eval}.\n\n"
        md += f"Looking at the stress (KSI) trend leading up to this inaccuracy:\n"
        for index, row in cooker_moves.iterrows():
            if row['Ply'] == blunder_row['Ply']:
                md += f"- **Move {row['Move_Number']} (The Turning Point):** {row['Move_Played']} — **KSI: {row['KSI']}**\n"
            else:
                md += f"- Move {row['Move_Number']}: {row['Move_Played']} — KSI: {row['KSI']}\n"
    else:
        target_player = climax_obj1
        window_df = climax_obj2
        md += "---\n## 🌊 Peak Tension\n"
        md += f"*The period of highest sustained stress without a decisive error.*\n\n"
        md += f"While the game lacked a massive probabilistic blunder, the most intense phase for **{target_player}** occurred between moves {window_df['Move_Number'].iloc[0]} and {window_df['Move_Number'].iloc[-1]}.\n"
        md += "They navigated this complex sequence effectively:\n"
        for index, row in window_df.iterrows():
            md += f"- Move {row['Move_Number']}: {row['Move_Played']} *(Eval: {row['Eval']})* — **KSI: {row['KSI']}**\n"
    md += "\n"

    # 2.5 THE FINAL COLLAPSE
    if collapse_row is not None:
        md += "---\n## 📉 The Final Concession\n"
        md += f"*A significant evaluation drop in an already difficult position.*\n\n"
        
        start_eval = collapse_row['Eval']
        next_eval = collapse_row['Next_Ply_Eval'] if not pd.isna(collapse_row['Next_Ply_Eval']) else "Game Over"
        
        md += f"By **Move {collapse_row['Move_Number']}**, **{collapse_row['Player_Name']}** was already facing a lost position (Win Probability: {collapse_row['Win_Prob']:.1f}%).\n"
        md += f"The move **{collapse_row['Move_Played']}** further solidified the result, dropping the evaluation from {start_eval} to {next_eval}.\n\n"

    # THE DEEP TANK (Top 3 Thinks)
    md += "---\n## 🕰️ The Deep Tank\n"
    md += f"*The longest continuous thought processes of the game for each player.*\n\n"
    if tank_data is not None:
        for player, top_3_df in tank_data.items():
            color = top_3_df['Color'].iloc[0]
            md += f"**{player} ({color})**\n"
            for index, row in top_3_df.iterrows():
                time_str = format_clock(row['Time_Spent_Sec'])
                md += f"- Move {row['Move_Number']}: {row['Move_Played']} *(Time: {time_str})*\n"
            md += "\n"
    else:
        md += "No valid time data available for this game.\n\n"

    # UNPUNISHED BLUNDER
    blunder_A, blunder_B = unpunished_data
    if blunder_A is not None:
        md += "---\n## ⚖️ The Unpunished Inaccuracy\n"
        md += f"*A critical mistake that went uncapitalized due to practical complexity.*\n\n"
        md += f"On **Move {blunder_A['Move_Number']}**, **{blunder_A['Player_Name']}** made a significant inaccuracy (**{blunder_A['Move_Played']}**), dropping their Win Probability by {blunder_A['WP_Drop']:.1f}%.\n"
        
        intuitiveness = blunder_B['Intuitiveness']
        if intuitiveness < 40.0:
            int_text = "a move that was highly unintuitive and difficult to spot practically"
        elif intuitiveness < 70.0:
            int_text = "a move that required precise calculation to fully justify"
        else:
            int_text = "a relatively natural move, making this a rare unforced omission"
            
        md += f"However, capitalizing on this required **{blunder_B['Player_Name']}** to find **{blunder_B['Best_SF_Move']}**, {int_text} (Intuitiveness Score: {intuitiveness:.1f}/100).\n"
        md += f"Missing this narrow path, they played **{blunder_B['Move_Played']}** instead, immediately returning {blunder_B['WP_Drop']:.1f}% of the Win Probability back to their opponent.\n\n"

    # 3. DEEPEST FOG
    md += "---\n## 🌫️ The Deepest Fog\n"
    md += f"*The moment where human intuition and engine reality diverged the most.*\n\n"
    md += f"On **Move {fog_row['Move_Number']}**, **{fog_row['Player_Name']}** faced a highly unintuitive position.\n"
    md += f"- **Intuitiveness Score:** {fog_row['Intuitiveness']}/100 (Highly obscure to human pattern recognition)\n"
    md += f"- **Objective Best (Stockfish):** {fog_row['Best_SF_Move']}\n"
    md += f"- **Expected Human Move (Maia):** {fog_row['Best_Maia_Move']}\n"
    
    start_eval = fog_row['Eval']
    next_eval = fog_row['Next_Ply_Eval'] if not pd.isna(fog_row['Next_Ply_Eval']) else "Game Over"
    next_wp = fog_row['Next_Ply_WP'] if not pd.isna(fog_row['Next_Ply_WP']) else 100.0 - fog_row['Win_Prob']
    
    md += f"- **Before the Move:** The evaluation was {start_eval}.\n"
    if fog_row['CP_Loss'] <= 1.0:
        md += f"- **What Happened:** They played **{fog_row['Move_Played']}**, successfully navigating the complexity and holding the evaluation at {next_eval} (Opponent Win Prob: {next_wp:.1f}%).\n\n"
    else:
        md += f"- **What Happened:** Relying on human intuition proved costly here. They played **{fog_row['Move_Played']}**, and the evaluation dropped to {next_eval} (Opponent Win Prob: {next_wp:.1f}%).\n\n"

    # SHARED PERCEPTION
    opt_rows, pess_rows = perception_data
    md += "---\n## 🧠 Shared Perception (Optimism & Pessimism)\n"
    md += f"*Moments where the human evaluation of the position deviated significantly from a zero-sum reality.*\n\n"
    
    if opt_rows is not None:
        opt_w = opt_rows.iloc[0]
        opt_b = opt_rows.iloc[1]
        sum_opt = opt_w['Awareness_WP'] + opt_b['Awareness_WP']
        md += f"**Peak Mutual Optimism (Move {opt_w['Move_Number']}):**\n"
        md += f"The board reached its most double-edged practical state. The data suggests **{opt_w['Player_Name']}** evaluated their chances at {opt_w['Awareness_WP']:.1f}%, while **{opt_b['Player_Name']}** evaluated their own chances at {opt_b['Awareness_WP']:.1f}%.\n"
        md += f"The combined perception of {sum_opt:.1f}% indicates that both players felt more optimistic than a zero-sum reality dictates, despite the objective evaluation remaining at {opt_w['Eval']}.\n\n"
    else:
        md += f"**Peak Mutual Optimism:** No significant moments of mutual, zero-sum delusion (Combined Perception > {MIN_MUTUAL_OPTIMISM}%) were detected.\n\n"
        
    if pess_rows is not None:
        pess_w = pess_rows.iloc[0]
        pess_b = pess_rows.iloc[1]
        sum_pess = pess_w['Awareness_WP'] + pess_b['Awareness_WP']
        md += f"**Peak Mutual Doubt (Move {pess_w['Move_Number']}):**\n"
        md += f"Conversely, the game reached a state of peak practical pessimism. The data suggests **{pess_w['Player_Name']}** evaluated their chances at {pess_w['Awareness_WP']:.1f}%, and **{pess_b['Player_Name']}** evaluated theirs at {pess_b['Awareness_WP']:.1f}%.\n"
        md += f"The combined perception of {sum_pess:.1f}% points to a tense, unclear position where both players felt worse than objective reality dictated, seeing 'ghosts' in an evaluation of {pess_w['Eval']}.\n\n"
    elif opt_rows is not None: 
        md += f"**Peak Mutual Doubt:** No significant moments of mutual pessimism (Combined Perception < {MAX_MUTUAL_PESSIMISM}%) were detected.\n\n"
    elif opt_rows is None and pess_rows is None:
        md += f"No significant moments of mutual delusion (Combined Perception > {MIN_MUTUAL_OPTIMISM}% or < {MAX_MUTUAL_PESSIMISM}%) were detected in this game.\n\n"

    # BURDEN OF PRECISION
    if burden_data[0] is not None:
        burden_window, safe_player, safe_avg, burden_player, burden_avg = burden_data
        md += "---\n## ⚖️ The Burden of Precision\n"
        md += f"*Asymmetrical practical difficulty over a sustained period.*\n\n"
        
        start_move = burden_window['Move_Number'].iloc[0]
        end_move = burden_window['Move_Number'].iloc[-1]
        avg_eval = burden_window['Eval_Num'].mean()
        
        md += f"Between Moves {start_move} and {end_move}, the objective evaluation remained relatively balanced (averaging {avg_eval:+.2f}). However, the practical difficulty was heavily one-sided.\n\n"
        md += f"**{safe_player}** enjoyed an average Forgiveness score of {safe_avg:.1f} across these {BURDEN_WINDOW_MOVES} moves, affording them multiple safe options. "
        md += f"Conversely, **{burden_player}** operated at an average Forgiveness of {burden_avg:.1f}, requiring prolonged, absolute precision to survive the sequence and maintain the balance.\n\n"

    # 4. TIGHTROPE WALK
    md += "---\n## 🧗 The Tightrope Walk\n"
    md += f"*Navigating a position with minimal margin for error.*\n\n"
    tr_player, tr_window = tightrope_data
    if tr_window is not None:
        start_tr = tr_window['Move_Number'].iloc[0]
        end_tr = tr_window['Move_Number'].iloc[-1]
        md += f"Between Moves {start_tr} and {end_tr}, **{tr_player}** was forced to find highly precise moves to maintain the position.\n"
        md += f"Over this {len(tr_window)}-move sequence, {tr_window['Is_Fragile'].sum()} moves required exact calculation (low forgiveness):\n"
        for index, row in tr_window.iterrows():
            marker = "🔥" if row['Forgiveness'] <= TIGHTROPE_FORGIVENESS_THRESHOLD else "✅"
            md += f"- Move {row['Move_Number']}: {row['Move_Played']} {marker} *(Forgiveness: {row['Forgiveness']:.1f})*\n"
    else:
        md += "No sustained periods of extreme precision (80%+ of moves with Forgiveness < 20.0 over a 3+ move sequence) were detected in this game.\n"
    md += "\n"

    # 5. CHAOS TRAPS
    md += "---\n## 🧩 Practical Complications\n"
    md += f"*Moves that challenged the opponent's human intuition rather than playing the objective board.*\n\n"
    if successful_trap is not None:
        md += f"🎯 **The Practical Success:** On Move {successful_trap['Move_Number']}, **{successful_trap['Player_Name']}** played **{successful_trap['Move_Played']}** instead of the engine's preferred {successful_trap['Best_SF_Move']}. This created practical difficulties, resulting in an immediate evaluation drop from the opponent.\n\n"
    else:
        md += "No significant practical complications (sub-optimal moves that induced an immediate blunder) were noted in this game.\n\n"

    # 6. VERTIGO SPIKE
    md += "---\n## 🌀 The Vertigo Effect\n"
    md += f"*The psychological friction of converting a winning advantage.*\n\n"
    if vertigo_row is not None:
        intensity = int((vertigo_row['Vertigo_Multiplier'] - 1.0) * 100)
        md += f"On **Move {vertigo_row['Move_Number']}**, **{vertigo_row['Player_Name']}** held a dominant position (Win Probability: {vertigo_row['Win_Prob']:.1f}%).\n"
        md += f"However, upon playing **{vertigo_row['Move_Played']}**, their stress metrics temporarily spiked:\n"
        md += f"- **Vertigo Intensity:** {intensity}% (Indicates friction in conversion)\n"
        md += f"- **Stress (KSI):** {vertigo_row['KSI']:.1f} / 100\n"
        md += f"Despite the strong objective evaluation ({vertigo_row['Eval']}), this moment required extra psychological effort to maintain control.\n"
    else:
        md += "No significant conversion friction (Vertigo spikes) was detected in this game.\n"
    md += "\n"

    # 7. THE CRUCIBLE
    md += "---\n## ⏳ Time Pressure\n"
    md += f"*How the clock influenced the decision-making process.*\n\n"
    crucible_player, crucible_moves = crucible_data
    if crucible_player is not None:
        peak_row = crucible_moves.iloc[-1]
        md += f"The clock became a significant factor for **{crucible_player}**, peaking around **Move {peak_row['Move_Number']}**.\n"
        md += "The moves played under this time restriction:\n"
        for index, row in crucible_moves.iterrows():
            if row['Ply'] == peak_row['Ply']:
                md += f"- Move {row['Move_Number']}: {row['Move_Played']} *(Clock: {format_clock(row['Clock_Seconds'])})* — **Time Pressure Score: {row['Time_Pressure']}**\n"
            else:
                md += f"- Move {row['Move_Number']}: {row['Move_Played']} *(Clock: {format_clock(row['Clock_Seconds'])})* — KSI: {row['KSI']:.1f}\n"
    else:
        md += "No severe time scrambles (Time Pressure > 40) were detected in this game.\n"
    md += "\n"

    # 8. IRON MIND
    md += "---\n## 🛡️ Objective Resilience\n"
    md += f"*Finding the best moves despite a lost evaluation.*\n\n"
    iron_player, iron_len, iron_df = iron_mind_data
    if iron_player is not None:
        start_iron = iron_df['Move_Number'].iloc[0]
        
        start_eval_num = iron_df.iloc[0]['Eval_Num']
        end_eval_num = iron_df.iloc[-1]['Next_Ply_Eval_Num']
        
        if iron_df.iloc[0]['Color'] == 'White':
            cp_gain = end_eval_num - start_eval_num
        else:
            cp_gain = start_eval_num - end_eval_num
            
        start_eval_str = iron_df.iloc[0]['Eval']
        end_eval_str = iron_df.iloc[-1]['Next_Ply_Eval'] if not pd.isna(iron_df.iloc[-1]['Next_Ply_Eval']) else "Game Over"

        md += f"Even with a heavily disadvantageous position, **{iron_player}** demonstrated strong defensive calculation. Starting on Move {start_iron}, they played **{iron_len} consecutive top-engine moves**.\n\n"
        
        if cp_gain >= IRON_MIND_MIN_IMPROVEMENT:
            md += f"This sequence successfully improved the evaluation from {start_eval_str} to {end_eval_str}, prolonging the game and testing the opponent's conversion technique.\n"
        elif cp_gain >= -0.5:
            md += f"By finding these critical moves, they managed to temporarily halt the decline, holding the evaluation steady around {end_eval_str}.\n"
        else:
            md += f"While these moves were objectively best, the position was too difficult to salvage, and the evaluation continued to decline from {start_eval_str} to {end_eval_str}.\n"
    else:
        md += "No sustained defensive sequences (2+ best moves while objectively lost) were detected.\n"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(md)
    print(f"✅ Success! Storyboard generated: {filename}")

# =============================================================================
# 6. MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a KSI Storyboard from a CSV.")
    parser.add_argument("filepath", help="The path to your CSV file")
    parser.add_argument("--out", help="Path to save the output markdown file.", default=None)
    args = parser.parse_args()
    
    print(f"⏳ Processing {args.filepath}...")
    df = load_data(args.filepath)
    
    if df is not None and not df.empty:
        tape_stats = get_tale_of_the_tape(df)
        
        climax_data = get_climax(df)
        is_blunder = climax_data[0]
        blunder_row = climax_data[1] if is_blunder else None
        collapse_row = get_final_collapse(df, blunder_row)
        
        tank_data = get_deep_tank(df)
        unpunished_data = get_unpunished_blunder(df)
        burden_data = get_burden_of_precision(df)
        perception_data = get_shared_perception(df)
        
        fog_row = get_deepest_fog(df)
        tightrope_data = get_tightrope_walk(df)
        successful_trap = get_chaos_traps(df)
        vertigo_row = get_vertigo_spike(df)
        crucible_data = get_crucible(df)
        iron_mind_data = get_iron_mind(df)
        
        generate_markdown(
            df, tape_stats, climax_data, collapse_row, tank_data, fog_row, 
            tightrope_data, successful_trap, vertigo_row, crucible_data, 
            iron_mind_data, unpunished_data, burden_data, perception_data, 
            args.filepath, args.out
        )
    else:
        print("❌ Error: Dataframe is empty or could not be processed.")