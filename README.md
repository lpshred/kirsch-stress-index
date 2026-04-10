# The Kirsch Stress Index (KSI)

## Introduction
The goal of the Kirsch Stress Index (KSI) is to measure the psychological stress level of a chess player at any given point of a game. It operates on a simple 0-100 scale, where `0` is equivalent to a dead-drawn endgame and `100` is the agonizing final moments just before resignation or blundering away a won game.

## The Components
KSI is the combination of several individual metrics:

1. **Fragility** - *How much will an inaccurate move hurt me?* Calculated as an exponentially weighted drop-off across Stockfish's top 10 moves.
2. **Forgiveness** - *What's my margin for error?* Calculated as the percentage of moves that won't drop a player's Stockfish win probability by more than 5% or completely to 0%.
3. **Intuitiveness** - *How hard are the best moves to find?* Calculated as the difference in win probability between Stockfish's absolute best moves and Lc0/Maia's most probable human moves.
4. **Desperation** - *How bad is the position for me?* Calculated by how far below 40% a player's Stockfish win probability has fallen.
5. **Time Pressure** - *How low am I on the clock?* Calculated dynamically based on the time remaining to make a move with consideration for the time control like the time per move until a time extension (i.e. FIDE Classical).
6. **Disparity Multiplier** - *How far behind on the clock am I?* Calculated as the relative difference in time remaining between the two players.
7. **Dread Factor** - *How close am I to losing outright?* Derived from Desperation, but used to dynamically shift the weights of the formula as the reality of a loss sets in.
8. **Vertigo Multiplier** - *How terrified am I of blowing this lead?* Calculated by how far above 90% a player's perceived win probability is.
9. **Objective Resilience** - *How strong is my objectivity under pressure?* Calculated based on where a player's rating sits between Stockfish (The Truth) and Maia (The Human Perception).
---

## Interpreting the Output

All base metrics are scaled from **0 to 100**. We use non-linear mathematical stretching to ensure that subtle psychological shifts in the middlegame are highly visible.
*Note on Evaluation: The master Evaluation at the top of the screen uses standard Absolute notation (+ is good for White, - is good for Black). However, inside the Top 5 Move tables, the 'WP Drop' and 'CP Drop' are shown relatively. A negative number here simply means 'how much worse this move is compared to the absolute best move,' regardless of which color is playing.*

### 🌡️ Kirsch Stress Index (Overall Temp)
*The master metric. The weighted sum of all psychological factors, reflecting both the anxiety of a tightrope walk and the despair of a lost position.*
* **00 - 40** 🟦 **Calm Waters:** Standard opening theory or a dead-drawn endgame.
* **40 - 65** 🟨 **Rising Tension:** The middlegame is complex, or the player is slightly worse and feeling the squeeze.
* **65 - 85** 🟧 **High Pressure:** Navigating a tactical minefield or grinding out a miserable defense in a clearly lost position.
* **85 - 100** 🟥 **The Breaking Point:** Busted position, extreme time trouble, or facing a trap where only one highly unnatural move saves the game. Resignation territory.

### 🔍 Fragility (The "Cliff")
*How steep is the drop-off if you don't find the absolute best move?*
* **00 - 30** 🟦 **Flat Ground:** The top engine moves are all roughly equal.
* **30 - 60** 🟨 **Noticeable Drop:** There is a clear "best" move, but alternatives aren't instantly losing.
* **60 - 100** 🟥 **Razor-Thin Tightrope:** If the player doesn't find the #1 move, their Win Probability plummets immediately.
> 💡 **Survival Fragility:** In a dead-lost position, Win Probability drops to 0%, meaning the WP cliff disappears. To account for the stress of "playing for a swindle," Fragility dynamically crossfades to measure *Centipawn* drops instead. Even if a player has a 0% chance to win, the stress of finding a -4.0 move instead of a -9.0 forced mate is still captured on the graph.

### 🌀 Forgiveness (The Margin of Error)
> 💡 **Crucial Note:** High Forgiveness **LOWERS** the overall KSI. It acts as a cooling mechanism.
* **00 - 30** 🟥 **Zero/Low Forgiveness:** A sharp tactical puzzle. *(Note: If a player is completely lost, Forgiveness drops to 0, because no moves are forgiving).*
* **30 - 70** 🟨 **Moderate Forgiveness:** 2 to 4 of the top 10 moves are perfectly acceptable to play.
* **70 - 100** 🟦 **Total Forgiveness:** Dead-drawn or completely crushing (+6.0). Almost any legal move maintains the advantage.

### 🧠 Intuitiveness (Human vs. Engine)
*Does the human instinct (Maia) match the cold, hard engine truth (Stockfish)?*
* **80 - 100** 🟦 **Highly Intuitive:** The human instinct matches the engine truth perfectly. Easy to play.
* **40 - 80** 🟨 **Tricky:** The human instinct is slightly off from the absolute best engine continuation.
* **00 - 40** 🟥 **"Alien" Position:** The moves that look incredibly natural to a human are actually massive blunders. High stress, as the player's instincts are betraying them.

### 😰 Desperation (The Weight of Losing)
*The looming dread of a bad evaluation. It only activates when the player's Win Probability drops below 40%.*
* **00** ⬜ **Balanced/Winning:** The player holds the advantage.
* **01 - 40** 🟨 **Slight Disadvantage:** The opponent has the edge (-0.2 to -0.8 eval). Causes a sharp initial spike in anxiety.
* **40 - 75** 🟧 **Clearly Losing:** Down material or structurally busted (-1.0 to -3.5 eval). Desperately hoping for a swindle.
* **75 - 100** 🟥 **Dead Lost:** -4.0+ advantage or forced mate. The player is just going through the motions and hoping for a miracle.

### ⏱️ Time Pressure (The Ticking Clock)
*How low am I on the clock, and is my opponent waiting for me to flag?*
* **00 - 30** 🟦 **Comfortable:** Plenty of time relative to the current time control.
* **30 - 70** 🟨 **Clock Awareness:** Falling behind the required pace. The clock is actively becoming a factor.
* **70 - 100** 🟥 **Time Scramble:** Extreme pressure. Surviving purely on increment or blitzing out moves to reach a time extension.
> 💡 **The Disparity Multiplier:** Time pressure is much more stressful when it's one-sided. If you are in a time scramble and your opponent has significantly more time on their clock, your Time Pressure value is multiplied by up to 1.5x.

### 💻 Top 5 Engine Truth (Stockfish)
*The cold, hard, objective reality of the board.*
This block displays the top 5 moves calculated by Stockfish. To prevent the engine from hanging on complex endgame mate calculations, Stockfish is given a strict 2.0-second time limit per turn (which typically reaches Depth 20+ on modern hardware). It is sorted by objective strength.
* **Evaluation & WP Drop:** Shows the traditional centipawn evaluation and how much your Win Probability will drop if you play this move instead of the absolute best move. (This is a direct visualization of the **Fragility** cliff).
* **Human Prob:** Shows how likely a human is to actually play this move, according to Maia. If the top engine move has a 2% human probability, you are in a highly unintuitive position.

### 🧍 Top 5 Human Instinct (Maia)
*The "Fog of War." What moves look the most natural to a human player?*
This block displays the top 5 moves according to the Maia neural network, sorted by how likely a human is to play them. 
* By comparing this block to the Engine Truth block, you can see if a player's natural instincts are about to lead them into a trap. If the #1 Human move results in a massive Win Probability drop, the **Intuitiveness** of the position is very low.

### 🔥 Top 5 Chaos Moves
*Which moves will inflict the most psychological damage on your opponent?*
This block simulates the next turn to find the moves that will spike the opponent's KSI the highest. It is sorted by the predicted change in the opponent's Temperature (e.g., `+21.9°C`).
* **Risk:** How much objective evaluation (in centipawns) you sacrifice by playing this move instead of Stockfish's #1 move.
* **Reward:** How much objective evaluation you stand to gain if your opponent falls for the trap and plays their most likely *Human Instinct* response instead of the perfect Stockfish response.
* **Ratio:** The Reward divided by the Risk. 
  * 🟩 **Infinite / High:** The move is objectively sound (zero/low risk) but sets a nasty trap. Free pressure.
  * 🟧 **Moderate (0.1 to 1.0):** A true gambit. You are taking on objective risk for the chance to confuse or break your opponent.
  * 🟥 **Low (< 0.1):** Hope chess. You are blundering your position away on the incredibly slim chance your opponent blunders worse.

> ⚠️ **Disclaimer on Predictive Discrepancies:** To keep the script running fast enough for live broadcasts, the Chaos Simulator calculates these future metrics using a blistering **0.5-second** search and a narrower **Top 5** move width, while actual turns are calculated with a full **2.0-second** search and a **Top 10** move width. Because of this "Horizon Effect" and simulated tunnel vision, the predicted KSI spike and Win Probability for a Chaos Move might be slightly different than the *actual* metrics once the opponent's turn officially begins. View this block as "Predictive Stress" rather than absolute truth.
---

## 🛠️ Installation & Setup

KSI runs locally on your machine. Because it uses powerful chess engines to evaluate human psychology, there is a one-time setup process. **No coding experience is required.**

### Step 1: Install Python & KSI
1. Ensure you have [Python 3.8+](https://www.python.org/downloads/) installed. 
2. Clone this repository (or download it as a ZIP file):
   ```bash
   git clone https://github.com/YOUR-USERNAME/kirsch-stress-index.git
   cd kirsch-stress-index
   ```
3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

### Step 2: Download the Engines (Stockfish & Maia)
KSI requires two engines to calculate psychological stress: **Stockfish** (to find the cold, objective truth of a position) and **Lc0 + Maia** (a neural network trained on millions of human games to predict what a *human* would actually do).

**1. Stockfish:**
* Download the latest Stockfish binary for your operating system from the [official website](https://stockfishchess.org/download/). (AVX2 recommended for modern CPUs).
* Extract all of the files and place them into the `engines/stockfish/` folder.

**2. Lc0 (Leela Chess Zero) & Maia Weights:**
* Download the latest Lc0 release for your system from the [Lc0 GitHub](https://github.com/LeelaChessZero/lc0/releases).
* Download the **Maia 2200** weights file (`maia-2200.pb.gz`) from the [Maia Chess website](https://lczero.org/play/networks/sparring-nets/).
* Place all of the `lc0` files and the `maia-2200.pb.gz` file into the `engines/lc0/` folder.

*(Note: If you place the engines in these exact folders, the script will find them automatically! If you put them somewhere else, you will need to manually pass their paths using the `--sf`, `--lc0`, and `--weights` flags).*

---

## 🚀 Usage

The entire KSI suite is controlled by a single master wrapper script: `ksi.py`. It handles all file management, automatically launches the web dashboard, and generates narrative storyboards. It features three distinct modes depending on how you want to analyze a game.

### 1. Live Mode (Real-Time Broadcasts)
*Best for: Watching a live tournament (like the Candidates) with a real-time dashboard on your second monitor.*

Provide a direct URL to a live-updating PGN (like a Lichess broadcast). KSI will continuously download the moves, evaluate them the second they are played, and host a live-updating web dashboard.

```bash
python ksi.py --mode live --url "https://lichess.org/api/broadcast/game/url.pgn"
```
*Once running, the script should automatically open your web browser to `http://127.0.0.1:8050/` to watch the live KSI graph.*
*For in progress games, the script will start up at the most recent move. To calcuate metrics starting from the beginning of the game, pass in the `--no-ff` flag.*


### 2. Full Mode (Batch Processing Finished Games)
*Best for: YouTube reviewers or deep-diving into a completed game.*

Provide a local PGN file. KSI will process the entire game from start to finish. Once complete, it will automatically open a **Markdown Storyboard** detailing the psychological turning points of the match, launch the interactive dashboard, and save all data neatly into a new folder inside the `games/` directory.

```bash
python ksi.py --mode full --pgn sample_game.pgn --fast
```
*(Note: It is highly recommended to use the `--fast` flag for full games. This skips the heavy Chaos Move simulations, reducing the processing time of a full game from ~15 minutes down to ~2 minutes).*

### 3. Archive Mode (Instant Dashboard Loading)
*Best for: Reviewing games you've already processed.*

If you want to look at a game you processed yesterday, you don't need to re-run the engines. Just point Archive Mode at the game's folder inside your `games/` directory, and it will instantly load the dashboard and storyboard.

```bash
python ksi.py --mode archive --dir games/PlayerA_vs_PlayerB_20260410_093922
```

### Optional Arguments
You can customize the engine's behavior by passing these flags to `ksi.py`:
* `--fast`: Skips the Chaos Move simulations. Crucial for fast processing of finished games.
* `--tc classical`: Sets the time control engine. Options are `classical` (FIDE 120m/40 moves), `rapid`, `blitz`, or `auto`. Defaults to `auto`.
* `--no-ff`: Disables fast-forwarding in live mode, forcing the engine to analyze and log every historical move before catching up to the live edge.
* `--threads 8`: Allocates specific CPU threads to Stockfish (highly recommended for performance). Defaults to 8.
* `--poll 3`: Changes how often the script checks the live URL for new moves (in seconds). Defaults to 3.

---

## The Calculation

The first 5 metrics are converted to a 0-100 scale. The metrics are then initially weighted in my best approximation of how much they matter to a high-level player, then summed to give an initial KSI. 

```python
w_frag = 0.25
w_int  = 0.20
w_dsp  = 0.25
w_forg  = 0.20 
w_tp   = 0.10 

ksi = (w_frag * fragility) + (w_forg * (100 - forgiveness)) + (w_int * (100 - intuitiveness)) + (w_dsp * desperation) + (w_tp * time_pressure)
```

### The Time Pressure Engine

Time Pressure is not a simple static threshold as it scales dynamically based on the game's time control. 

For games under the FIDE Classical time control, the engine tracks the mumber of moves to reach move 40. If a player's average time per remaining move drops below 90 seconds, the Time Pressure metric begins to rise, maxing out when the player reaches 15 seconds per move. After move 40, the Time Pressure metric reverts to a sudden-death threshold (activating with under 5 minutes total remaining). 

Additionally, the Time Pressure metric utilizes a Disparity Multiplier. If a player is experiencing Time Pressure (Base TP > 0) and their opponent has a significant clock advantage, the raw Time Pressure value is multiplied. The multiplier activates when the opponent has > 1.25x more time, and maxes out at a 1.5x penalty when the opponent has 4.0x more time. This models the creeping dread of being in a time scramble while your opponent has plentiful time to calculate their counter lines. Conversely, the Disparity Multiplier has little effect when both players have plenty of time and a time scramble is not imminent for either player.

The formula for this is quite complex, especially accounting for multiple time controls, so it is omitted from the readme.

### Game State Adjustments

This formula works well for normal play situations. However, it starts to collapse once the game is in a clearly won or lost position. Empirically, these games are already decided, so there's no objective tension. But psychologically to a human player (which is exactly what KSI is trying to measure), these are still very stressful situations. To compensate for this, a Dread Factor was added for losing players and a Vertigo Multiplier was added for winning players.

These adjustments are blended in gradually and capped at a player's skill level. This helps avoid arbitrary cutoffs and conveniently allows for differentiation between the skill of the players based on their rating.  This skill floor is referred to as Objective Resilience and it models a player's resistance to the effects "Fog of War" and Desperation/Dread.

### Objective Resilience

A player's Objective Resilience is calculated based on where their current Elo rating falls between the ratings of our objective truth (Stockfish at 3600) and our human analog (Maia at 2200). This method was chosen originally to model how much each engine should be weighted when trying to determine the player's mental state in the fog of war calculations. It was then re-used in the Dread Factor adjustments to represent how much of their objectivity a player can maintain in completely lost positions. With that adaptation, Object Resilience has become an approximation of a player's skill floor based on their rating. This assumes that finding complex lines and salvaging lost positions roughly scales with player rating. Considering the importance of both of those skills in winning chess games, the assumption seems appropriate. 

 The value is a simple percentage calculated using the formula below:

```python
obj_resilience = (player_elo - maia_elo) / (stockfish_elo - maia_elo)
```

### Applying the Modifiers

Now that a player's skill floor and awareness of their own WP is defined, their KSI can be adjusted for the perceived game state.

#### Dread Factor (Losing)

When a player is losing, their psychological goal shifts from winning the game to surviving it. The Dread Factor is used to adjust the *weights* (not the raw values) of certain metrics when a player's desperation activates (Stockfish WP drops below 40%) and is playing from behind. The objective in chosing the activation threshold was to identify a position as "slightly" worse. Games open with a roughly 45% WP for black, so 40% was a round number slightly worse than the starting position. 

As the Dread Factor rises, the weight of the Desperation metric is increased to match the creeping reality of losing, while the weights of Fragility and Intuitiveness are drained to match the falling importance of finding the right moves when the situation can't get much worse. 

However, a player's objective focus cannot be drained completely. We use the player's Objective Resilience (skill floor) to ensure that their Dread Factor can only drain SOME, not ALL, of their board-state weights. This attempts to model their ability to find game saving moves even in the worst positions. It also allows the formula to account for a relative difference in skill levels between players in a game. 

The Intuitiveness metric is drained completely as the Dread Factor approaches 100%. In hopelessly lost positions, Stockfish and Maia agree that there are no good options. This models the fact that once there is no longer any confusion about the board state as the player is instead filled with desperation.

The Fragility metric is only drained partially as the Dread Factor approaches 100%. This is done to allow a small amount of hope that the player might hang on long enough to set a trap or force a blunder from their opponent. The player's Objective Resilience is used here as the skill floor for the Fragility metric to ensure it doesn't collapse completely.

The calculation for how the weights are adjusted for the Dread Factor is shown below:

```python
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
```

#### Vertigo Multiplier (Winning)

The Vertigo Multiplier is used to adjust the *values* (not the weights) of certain metrics when a player is in a winning position. As the Vertigo Multiplier rises, the raw values of Fragility and Intuitiveness are multiplied (up to the max of 100) to match the increased pressure to avoid blunders while in a winning position. 

Stockfish generates a WP based on perfect play, but the goal of KSI is to measure human perception, not theoretical accuracy. Stockfish might see an unintuitive winning line that a human completely misses. If a human doesn't see it, it won't affect their stress level—which is crucial to the goal of KSI. To compensate for this we use a player's Objective Resilience to calculate their awareness of their own winning chances.

##### Human Awareness of Win Probability ("Fog of War")

A player's awareness of their WP is measured differently depending on whether the player is winning or losing. This stems from the assumption that players are better at sensing when they're behind than they are at identifying complex winning chances. 

For losing players, the unadjusted Stockfish WP is used to calculate the Desperation and Dread Factor metrics. Sensing a losing position is more intuitive, and it acts as a harsh reality check for players because at the end of the day, checkmate is checkmate whether you realize it ahead of time or not. 

For winning players however, it's more complicated. If a player doesn't notice an opportunity to punish their opponent's mistake, it won't affect their stress level. Accounting for human imperfections requires an approximation of a human's awareness of their own WP. To do this, a player's Objective Resilience is used to model where a player sits between Stockfish's absolute truth and Maia's human flaws to model how well a player can see through the "Fog of War" and find these winning chances.

Further, some positions are easier to evaluate than others. To compensate for this, the baseline Stockfish and Maia weights are adjusted as the Intuitiveness metric rises and falls. As the board becomes easier to read, Stockfish becomes weighted more heavily. As the board becomes an alien mess, Maia becomes weighted more heavily to account for the likelihood that a player is relying on their human instincts. However, a player's Stockfish weight (objective truth) will NEVER drop below their base Objective Resilience to account for their overall skill floor and skill floor relative to their opponent.

Taking all of this into account, the formula for determining a winning player's awareness of their WP is:

```python
# 1. Adjust Vision based on the Intuitiveness metric
adjusted_vision = base_resilience + ((1.0 - base_resilience) * (Intuitiveness / 100))

# 2. Calculate the blended perceived win probability
Perceived_WP = (adjusted_vision * Stockfish_WP) + ((1.0 - adjusted_vision) * Maia_WP)
```
##### Vertigo Activation

Human beings are risk-averse by nature which favors conservative decision making. Psychology studies show that human brains the pain of losing differently than the joy of winning. The choices of 40% WP as the threshold for losing and using the reality of Stockfish in the evaluation were deliberate choices to model that humans are more aware of the fact that they're losing and that reality did not need an adjustment to account for that. The player's, especially at the GM level, can sense it. Since winning feels different, this formula calculates it differently. 

First, the threshold for a winning position is more than just "slightly" or "definitely" better. The goal is to identify truly winning positions for a human. This formula operates under the assumption that it's easier to sense a losing position than a winning one, therefore something stronger than the 60/40 split used for Dread Factor is needed. Converting the win more often than not is as good of a starting point as any for determining when a player's mindset shifts from avoiding a loss to chasing a win. Data shows that humans can convert Stockfish's 90% WP (based on engine vs engine play) about 70% of the time in real life, so 70% WP was chosen as the threshold to apply the Vertigo Multiplier.  

Second, the Perceived WP calculated in the section above is used to evaluate whether or not the position is truly winning. This allows the formula to account for a player's Objective Resilience to fight the fog of war and "find" winning moves, but also reflects the fact that a blown lead isn't necessarily an outright loss. There's still the chance to play for a draw or regain the advantage. Compared to failing in a losing position, the pain of the cold reality is blunted by the softened penality for failure. The formula's use of Perceived WP instead of raw Stockfish WP is intended to model this intracacy.

Finally, to avoid allowing an opponent's blunder to artificially increase a player's KSI, the values are adjusted directly rather than weighting them more heavily in the formula. This allows Vertigo to amplify a player's KSI on a sub-optimal but tricky move, while blunting its effect on a low-risk blunder (already low initial Fragility won't be amplified much).

Once the game state and player mindsets changes are account for, the Vertigo adjustments are calculated via the formula below:

```python
vertigo_mult = 1.0
if perceived_wp > 90.0:
    vertigo_mult = 1.0 + ((perceived_wp - 90.0) / 10.0)

vert_adj_fragility = min(100.0, base_fragility * vertigo_mult)
vert_adj_intuitiveness = max(0.0, 100.0 - ((100.0 - base_intuitiveness) * vertigo_mult))
```

### The Final Formula - KSI
Once adjusted for the Vertigo Multiplier, the final KSI formula is:

```python
ksi = (dread_adj_w_frag * vert_adj_fragility) + (w_forg * (100 - forgiveness)) + (dread_adj_w_int * (100 - vert_adj_intuitiveness)) + (dread_adj_w_dsp * desperation) + (w_tp * time_pressure)
```

---

## Initial Inspiration

In designing KSI, I had several problems I wanted to solve.

For casual fans like me who rely on the evaluation bar for a sense of the game state, chess games appear to be even until one player blows it with a blunder. Watching a game framed as "two players trying not to lose" is far less exciting than watching two players trying to outplay each other. I wanted to go beyond the evaluation bar and make it easier for casual fans to see the human struggle and offensive side of chess, where players try to create winning chances, fight for their lives, and convert winning positions in long classical endgames. 

Because the evaluation bar considers only the most optimal moves, not all positions Stockfish evaluates as `0.00` are equal. Some have many easy-to-play lines to maintain an advantage. Others require long, unintuitive lines to avoid a losing position. My goal in creating KSI is to help casual fans see just how precarious or safe a player's situation actually is, regardless of what the evaluation bar says. It allows fans to visualize how one player's moves put pressure on their opponents by raising the stakes of their mistakes and reducing their margin for error. 

On the other hand, not all winning (or losing) positions are equal. While some positions might be easily won in solved endgames, others may require a player to find a single unintuitive line to punish what Stockfish feels is a significant blunder. The goal of KSI is to highlight the human element of one player desperately fighting to survive against a leading player desperate to convert their rare winning chances and avoid a disappointing draw.

If you're reading this, I hope that you're able to enjoy this project as much as I have. Whether it's as a casual fan, armchair psychologist, or statistics geek, I hope it brings joy to your life in one way or another as it has for me.

---

## Second Order Uses: The Chaos Metric

On its face, KSI is a simple metric for simple fans. It helps visualize what comes more intuitively to advanced players. However, there are applications beyond understanding a single game that may be of use to more advanced players. 

I believe there's immense value in identifying the moves that objectively put one's opponent under the most pressure. I also believe there is value in an objective measure of the risk and reward of a particular gambit. This information could be useful in the development of prepared lines for high-level tournament play. I thought so highly of this information that I included it in the script's default output.

Predicting the moves that will increase the opponent's KSI the most requires looking at a player's possible moves and measuring their opponent's KSI before and after the move. 

Often, the move that raises the opponent's KSI the most is not the objectively best move to play. That's the whole point of a gambit, after all. Once the relative change in KSI is known, the **Risk to Reward Ratio** can be calculated to determine if the move is worth playing. 

*   **The Risk:** Measures how sub-optimal the chosen move is compared to Stockfish's best move. This is how much the player will be punished if their opponent plays perfectly. 
*   **The Reward:** Measures the difference in Stockfish's evaluation if the opponent falls for Maia's most probable human move. 

In a nutshell, this is the best way I could think of to quantify "applying pressure", "creating winning chances", or "setting a trap". At this point, we've veered quite a bit from what statistical rigor KSI had originally. Still, I wanted to include this as an example of KSI's extended use cases and because it's just fun to root for chaos as a casual viewer. 

---

### A Note on Predictive Discrepancies (The "Fog of War")
If you watch the CLI output closely, you might notice that the predicted KSI increase for a Chaos Move doesn't always perfectly match the actual KSI on the ensuing turn. For example, the Chaos Metric might predict that playing `Kxh4` will raise the opponent's KSI by `+31.1` and maintain a `50.0%` Win Probability. However, when the opponent's turn actually begins, their KSI might only rise by `+29.3` and their WP might shift to `47.2%`. 

This is not a bug; it is a deliberate architectural compromise to allow this script to run in real-time during live broadcasts. 

1. **The Time & Width Compromise:** To calculate the Top 5 Chaos Moves, the script has to run the entire KSI evaluation engine 5 to 10 extra times per turn. If it gave Stockfish the full 2.0 seconds to look at 10 possible responses for each simulation, it would take over a minute to process a single late-game move. To keep it lightning fast, the Chaos Simulator applies "Tunnel Vision" and strict circuit breakers. It evaluates potential Chaos Moves using a strict **0.5-second time limit**, and reduces its peripheral vision to only evaluate the opponent's **Top 5** most likely responses instead of 10. This strict time management prevents the engine from locking up while trying to mathematically prove forced mates across multiple branching timelines. It is a narrow, fast "Fog of War" prediction versus the cold, wide reality of the actual turn.
2. **The Horizon Effect:** When Player A is thinking, Stockfish searches from *Player A's* position. When Player B's turn begins, the root node of the board advances, allowing Stockfish to slightly deeper into the game tree. This frequently causes slight shifts in the "Absolute Truth" of the Evaluation and Win Probability.
3. **Time Pressure Isolation:** During a Chaos Simulation, the script assumes the opponent has 10 minutes on the clock, temporarily disabling the Time Pressure metric. This is done to isolate the pure *board stress* of a move, rather than conflating it with the opponent's clock situation. When the actual turn begins, the opponent's true clock time is applied.

Ultimately, the Chaos Metric should be viewed as a highly educated guess of how much psychological stress a move will inflict once the position resolves.

---

## Opportunities for Improvement

### Better Human Move Probabilities
My initial goal was to model human move probabilities based on running a Monte Carlo simulation through the Lc0/Maia engine to dynamically calculate the probabilities in real-time. Unfortunately, the UCI Python library this script uses makes it incredibly difficult to extract raw neural network policy weights from Maia. Instead, I had to use a rank-based exponential decay to determine the probability of Maia's top 5 moves. It's not perfect, but I'm satisified with the trade-off. True dynamic calculations would still be gold standard here. Getting that data would involve writing a custom library to interface with Lc0 directly, which I determined to be out of the scope of this project and well beyond my vibe-coding enhanced abilities.

### Better Player Rating Scaling
I built KSI and this script to help me follow the 2026 Candidates Tournament. Because of this, I chose the best Maia database I could find (2200 Elo) and hardcoded the baseline anchor to represent a 2800 Elo Super-GM. If you run this script on a 1500-rated game, it will apply the vision strength of a 2200-rated player to them. For better scaling, you would want to use a more appropriate Maia database and dynamically pass the players' ratings into the baseline formula. 

### Incorporating Tiredness
I considered including a metric for tiredness, as players often cite fatigue in interviews as explanations for their blunders or decisions to settle for a draw. I decided against implementing this because it felt too arbitrary, and both players have generally been playing the same amount of time. I was also nearing my own personal understanding limits for the growing complexity of this script. For someone more enterprising than myself, tiredness is likely the best new source of stress to incorporate into this metric next.

### Intent
As I worked though some games during testing, I often wondered if a sub-optimal move was a mistake or a carefully crafted prepared move or gambit. In my estimation, mistakes are more stressful than laying a trap, so I wanted to account for that in this metric. After some brainstorming, the only thing that could make any sense would be time taken before making a move. Still, I felt that there are many other reasons for long thinks and prepared moves wouldn't take far less think. Sometimes mistakes can come even after long thinks. As such, I decided not to implement intent. If there were a better way to do estimate intent, I think it would be a worthy addition to this formula.

---

## Credits
*   **Steve Kirsch** - Me, a casual chess fan who wanted to improve my understanding of the human elements of chess to better enjoy watching high-level GM games. I provided the inspiration, the vibe in vibe-coding, testing, documentation, and the publishing of this metric and scripts to generate and visualize it.
*   **Gemini 3.1 Pro Preview** - All Python code, all formulas, super-GM and general human psychology, interpretation guide, CLI usage guide, general copyediting of this readme file, and critical feedback and suggestions based on my inspiration and vibes.
*   **Fabiano Caruana, Wei Yi, Hikaru Nakamura, Matthias Bluebaum, Javokhir Sindarov, Praggnanandhaa Rameshbabu, Anish Giri, Andrey Esipenko** - For their many exciting 2026 Candidates Tournament games that were used during testing.
*   **Lichess** - The PGN files used during testing.
*   **Chess.com** - The UI I used to validate my initial suspicions that led to the inspiration for this project.
*   **Gothamchess** - For so eloquently explaining the human elements of high level chess that inspired me to try and capture them here for when your comentary isn't available
*   **Team Hikaru Broadcast** - Commentary and interviews to provide insight into super-GM psychology and perspective.
*   **Ashton Anderson, Jon Kleinberg, and Sendhil Mullainathan** - Authors of the 2017 paper *Assessing Human Error Against a Benchmark of Perfection*, which provided the mathematical foundation for measuring position difficulty via engine evaluation drop-off (adapted here as the Fragility metric).
*   **Dr. Kenneth Regan** - For his pioneering work on Intrinsic Chess Ratings and modeling the "forgiveness" of chess positions based on the breadth of viable engine moves (adapted here as the Forgiveness metric).
*   **Reid McIlroy-Young, Siddhartha Sen, Jon Kleinberg, and Shimon Whiteson** - The researchers behind the Maia Chess engine (2020), whose neural network weights model how humans see and play chess to make the "Human Fog" simulation possible (adapted here as the Intuitiveness metric) .
*   **Reality** - Because living life (or playing chess) on Reality's terms is much harder to do when the engine evaluates it at -6.0 (adapted here as the Desperation metric).
*   **Father Time** - Still undefeated and who's influence on the game is as relevant today as it ever was (adapted here as the Time Pressure metric).
*   **You** - For taking an interest in this pet project of mine.