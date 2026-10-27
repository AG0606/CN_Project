# 🔍 Your Doubts — Answered One by One

---

## 1. What exactly is a GNN and why are we using it here?

### Start from the basics: What is a Neural Network?

A neural network is just a **math function with adjustable knobs** (called "weights" or "parameters"). You feed it input numbers, it multiplies them, adds them, and transforms them through layers, and produces output numbers. By adjusting those knobs during "training," you teach it to produce useful outputs.

```
Input Numbers → [Multiply] → [Add] → [Transform] → [Multiply] → Output Numbers
                   ↑            ↑                        ↑
              These knobs are "parameters" — the machine learns their values
```

### So what's a GRAPH Neural Network (GNN)?

A regular neural network treats each input independently. But our network nodes (France, Germany, Belgium, etc.) are **connected to each other** — they form a **graph**. A GNN is a neural network that **knows about these connections**.

The key idea is **neighbor aggregation**: each node collects information from its neighbors before making predictions.

**Concrete example in our project:**

France is connected to Germany, Belgium, Switzerland, and Luxembourg. When predicting France's future traffic:

- A regular neural network only looks at France's own past traffic
- A **GNN** looks at France's traffic **AND** also what Germany, Belgium, Switzerland, and Luxembourg are doing

```
                    Germany's traffic ──┐
                                        │
Belgium's traffic ──┐                   │
                    ├──→ COMBINE ──→ Predict France's future traffic
Switzerland's traffic──┘                │
                                        │
Luxembourg's traffic ──────────────────┘
                    │
France's own traffic ──────────────────→
```

**Why?** Because traffic patterns are correlated across neighbors. If Germany suddenly gets a burst of traffic, some of it might flow through France. Knowing your neighbor's situation helps you predict your own future.

### The specific GNN layer we use: GCN (Graph Convolutional Network)

Our GCN does this mathematically:

```
For each node i:
    neighbor_info = A_normalized × all_node_features    (weighted average of neighbor features)
    combined = [own_features, neighbor_info]             (concatenate both)
    output = ReLU(Linear(combined))                     (transform through a learned layer)
```

`A_normalized` is the **normalized adjacency matrix** — a matrix encoding who is connected to whom, with proper scaling so nodes with many connections don't dominate.

---

## 2. What is GRU and how is it used here?

### The problem: we have a TIME SEQUENCE

Traffic at 9:00 AM, 9:15 AM, 9:30 AM, 9:45 AM, ..., 12:00 PM (12 bins = 3 hours).

We need to find **patterns over time** — "traffic has been rising for the last hour, so it'll probably keep rising."

### GRU = Gated Recurrent Unit

A GRU is a type of **recurrent neural network** that processes sequences one step at a time while maintaining a **memory** (called "hidden state"):

```
Step 1 (9:00 AM data)  →  GRU  →  memory₁ (remembers something about 9:00)
Step 2 (9:15 AM data)  →  GRU  →  memory₂ (remembers 9:00 + 9:15)
Step 3 (9:30 AM data)  →  GRU  →  memory₃ (remembers 9:00 + 9:15 + 9:30)
   ...
Step 12 (12:00 PM data) → GRU →  memory₁₂ (remembers the WHOLE 3-hour pattern)
                                     │
                                     v
                              Use this to PREDICT
                              12:15, 12:30, 12:45
```

The "gated" part means the GRU has learned **gates** that decide:
- **What to remember** from the past (important trends)
- **What to forget** (irrelevant old data)
- **What to update** with new information

### How GCN + GRU work together in our project:

```
Step 1: At each time step, GCN mixes neighbor information
        (spatial patterns — who's connected to whom)

Step 2: GRU processes the GCN outputs over 12 time steps
        (temporal patterns — how things change over time)

Step 3: A final layer predicts the next 3 time steps
```

**GCN captures SPACE (network structure). GRU captures TIME (traffic trends). Together they predict future traffic.**

---

## 3. What is Hysteresis?

### Simple analogy: A thermostat

Your AC turns ON when temperature hits 26°C. But it doesn't turn OFF the instant it drops to 25.9°C — it waits until it drops to, say, 24°C. This **reluctance to switch back and forth** is hysteresis.

### In our routing context:

Without hysteresis, the planner might do this:

```
Bin 1: "Path A is 2% cheaper in carbon → switch to A!"
Bin 2: "Wait, Path B is 1% cheaper now → switch to B!"
Bin 3: "Nope, A is cheaper again → switch to A!"
Bin 4: "B is cheaper! → switch to B!"
```

This **constant flipping** is bad because:
- Each route change can cause packet reordering/disruption
- The differences are tiny — not worth the instability

### Our hysteresis has two guards:

| Guard | Rule | Purpose |
|-------|------|---------|
| **Minimum improvement** | Don't switch unless new path is ≥ 5% better | Avoids switching for tiny gains |
| **Hold time** | After switching, keep the path for ≥ 2 bins (30 minutes) | Prevents rapid flip-flopping |

**Exception:** If the current path is at **capacity risk** (link about to overload), hysteresis is overridden — safety trumps stability.

---

## 4. What are "Candidate Paths per OD pair"?

### What is an OD pair?

OD = Origin-Destination. An OD pair is a specific traffic flow from one node to another.

Example: **Italy → Netherlands** is one OD pair.

### What are candidate paths?

For Italy → Netherlands, there might be **multiple possible routes** through the network:

```
Path 1: Italy → Switzerland → France → Belgium → Netherlands  (5 hops)
Path 2: Italy → Germany → Netherlands                         (3 hops, shortest)
Path 3: Italy → Germany → Belgium → Netherlands               (4 hops)
```

We precompute up to **3 shortest loop-free paths** per OD pair. These are the **candidates** the planner can choose from at each time step.

**Not all paths qualify.** We apply a **delay bound** of 1.5× the shortest path's delay. So if the shortest path takes 5 ms, any candidate taking > 7.5 ms is rejected. This ensures we don't route traffic through absurdly long detours just to save carbon.

---

## 5. The 8×8 matrix has 56 off-diagonal entries. Why only 6 active OD pairs?

### The 8×8 matrix

With 8 nodes, every node can send traffic to every other node. That's 8 × 8 = 64 entries. Subtract the 8 diagonal entries (a node sending to itself = 0), you get **56 possible directed OD pairs**.

### Why only 6?

Not all 56 pairs are interesting for our experiment. We select only 6 because:

1. **Many pairs have zero or near-zero traffic** in the historical data — nothing to study
2. **Some pairs only have ONE feasible path** — the planner has no choice, so there's nothing to compare
3. We need pairs with **≥ 2 candidate paths within the delay bound** — otherwise carbon-aware routing can't actually choose a different route

### How the 6 are selected (using ONLY training data):

```python
score(pair) = training_mean_demand × (1 + 0.25 × shortest_route_link_overlap)
```

Pick the 6 highest-scoring pairs that have ≥ 2 candidate paths. The overlap term favors pairs whose routes share links — that's where **congestion** happens and where routing choices actually matter.

### The 6 selected pairs:

| # | Origin | Destination | Why interesting |
|---|--------|-------------|----------------|
| 1 | Italy | Netherlands | High demand, shares links with others |
| 2 | Italy | France | High demand, multiple paths |
| 3 | Germany | Belgium | Medium demand, competing routes |
| 4 | Netherlands | France | Route overlap with pair 1 |
| 5 | Netherlands | Italy | Reverse of pair 1 |
| 6 | Switzerland | Germany | Shares links with Italian pairs |

**All other 50 OD pairs are masked** (set to zero). The simulation only generates and routes traffic for these 6 pairs. Results only apply to this subset.

---

## 6. Explain the Chronological Split Table

We have 3,972 traffic matrices (bins), each representing a 15-minute interval. We split them **in time order** (NOT randomly!) into three parts:

```
Timeline ──────────────────────────────────────────────────────►
         ◄──── Training (60%) ────►◄── Validation (20%) ──►◄── Test (20%) ──►
Rows:     0 ─────────────── 2,382   2,383 ──────── 3,176   3,177 ────── 3,971
Windows:        2,369                    780                    781
```

### What each split does:

| Split | Rows | Windows | What it's for | Who can look at it |
|-------|------|---------|---------------|--------------------|
| **Training** | 0–2,382 | 2,369 | Teach the GNN to predict traffic | The model during training |
| **Validation** | 2,383–3,176 | 780 | Tune settings, calibrate safety margin, pick best model checkpoint | You, to make decisions |
| **Test** | 3,177–3,971 | 781 | Final honest evaluation — report these numbers | Nobody until the very end |

### Why chronological (not random)?

In real life, you can't train on **future** data to predict the **past**. Random splitting would mix future and past data — that's **cheating**. Chronological splitting ensures the model only learns from data that came **before** what it's trying to predict.

### What is a "window"?

A window = 12 history bins + 3 target bins = 15 consecutive bins. We slide this window along the data:

```
Window 1:  [bin 0 ... bin 11] → predict [bin 12, 13, 14]
Window 2:  [bin 1 ... bin 12] → predict [bin 13, 14, 15]
Window 3:  [bin 2 ... bin 13] → predict [bin 14, 15, 16]
   ...
```

Windows that cross a **gap** (missing timestamp) or cross a **split boundary** are rejected. That's why 2,383 rows don't give 2,383 windows — some are lost to gaps and boundaries.

---

## 7. What does "7,672 parameters" mean? Explain Training, Epochs, Loss, Seed

### Parameters (7,672)

Parameters = the **adjustable numbers** inside the neural network. Think of them as **knobs** that the training process tunes.

In our GCN-GRU:

```
Spatial layer:   Linear(16 inputs → 32 outputs)  = 16×32 weights + 32 biases = 544
GRU layer:       GRU(32 → 32)                    = 3 × (32×32 + 32×32 + 32 + 32) = 6,336
Prediction head: Linear(32 → 24)                  = 32×24 weights + 24 biases = 792
                                                    ──────────────────────────────
                                                    Total: ~7,672 parameters
```

**Why this matters:** More parameters = more powerful but needs more data and time. 7,672 is **tiny** by ML standards (ChatGPT has billions). It runs easily on a CPU.

### Training — How the machine actually LEARNS

Training is an iterative process. Here's the full loop:

```
┌─────────────────────────────────────────────────────────┐
│                  THE TRAINING LOOP                       │
│                                                         │
│  1. FEED: Give the model a batch of 128 windows         │
│     Input: 12 bins of history                           │
│     The model outputs: 3 predicted future bins          │
│                                                         │
│  2. COMPARE: How wrong was it?                          │
│     actual_traffic - predicted_traffic = error          │
│     Loss = average |error| across all active pairs      │
│     (this is called MAE — Mean Absolute Error)          │
│                                                         │
│  3. LEARN: Adjust the 7,672 parameters to reduce error  │
│     Uses "backpropagation" — calculates which direction  │
│     each parameter should move to reduce the loss       │
│     Uses "Adam optimizer" — the specific algorithm       │
│     that decides HOW MUCH to adjust each parameter      │
│                                                         │
│  4. REPEAT for all batches in the training data         │
│     (one full pass = one EPOCH)                         │
│                                                         │
│  5. CHECK: After each epoch, test on VALIDATION data    │
│     If validation error improved → save this model      │
│     If no improvement for 8 epochs → STOP (patience)    │
│                                                         │
│  6. Final model = the saved checkpoint with lowest      │
│     validation error (NOT the last epoch)               │
└─────────────────────────────────────────────────────────┘
```

### Epoch

One **epoch** = one complete pass through ALL 2,369 training windows. Since batch size is 128, one epoch has about `2,369 / 128 ≈ 19 batches`.

We run up to **40 epochs** maximum, but stop early if the model hasn't improved for 8 consecutive epochs (**patience = 8**).

### Loss

Loss = the **single number** that tells you how wrong the model is. Lower is better.

Our loss is **MAE (Mean Absolute Error)** in Mbps:

```
Loss = average of |actual_traffic - predicted_traffic|
       across all active OD pairs, all horizons, all samples in the batch
```

Example: if the model predicted 5.0 Mbps but actual was 5.3 Mbps, the error for that one prediction is |5.3 - 5.0| = 0.3 Mbps.

### Seed (= 42)

A **random seed** fixes all the randomness in the process:
- Initial random parameter values
- The order in which training samples are shuffled
- Any random operations

**Why?** If you and I both run the training with seed 42, we get **exactly the same model**. This is **reproducibility** — essential for science. Without a fixed seed, every run would give slightly different results and you couldn't verify each other's work.

---

## 8. How is the training actually happening? (ML from scratch)

Let me walk through a **concrete simplified example**:

### Step 1: Initialize

The 7,672 parameters start at small random values (determined by seed 42). The model knows nothing yet — its predictions are garbage.

### Step 2: Forward Pass (make a prediction)

```
Input: 12 historical traffic matrices (3 hours of traffic data)

The model processes them:
  → GCN mixes each node with its neighbors' features
  → GRU reads the 12 time steps and builds a memory
  → Head produces 3 predicted matrices (next 45 min)

Output: predicted traffic for bins k, k+1, k+2
```

### Step 3: Compute Loss (how wrong is it?)

```
Actual future traffic:     [2.1, 3.5, 4.0] Mbps  (we know this from training data)
Model's prediction:        [1.8, 3.0, 5.2] Mbps  (model's guess)
Absolute errors:           [0.3, 0.5, 1.2]
Mean Absolute Error (Loss) = (0.3 + 0.5 + 1.2) / 3 = 0.667 Mbps
```

### Step 4: Backpropagation (figure out how to fix it)

This is the mathematical magic. The algorithm traces **backwards** through the network:

```
"The loss was 0.667. Parameter #4231 contributed to making the
 prediction too high by 1.2 Mbps. If I decrease parameter #4231
 by 0.001, the loss would drop by roughly 0.003."
```

It computes this **gradient** (direction of improvement) for ALL 7,672 parameters simultaneously using calculus (chain rule).

### Step 5: Update Parameters

The **Adam optimizer** adjusts each parameter:

```
parameter_new = parameter_old - learning_rate × gradient

With learning_rate = 0.001:
parameter #4231 was 0.527, gradient says -0.003
parameter #4231 becomes 0.527 - 0.001 × (-0.003) = 0.527003
```

Each individual adjustment is **tiny**, but over thousands of batches and 40 epochs, the model gradually learns to predict traffic accurately.

### Step 6: Repeat, check validation, save best

After each epoch, we test on the **validation set** (data the model has never trained on). If the validation error is the best we've seen → save this version of the model. If 8 epochs pass without improvement → stop training (the model has likely learned all it can).

### Analogy

Imagine learning to throw darts blindfolded:
- **Forward pass** = throwing the dart
- **Loss** = how far from the bullseye
- **Backpropagation** = someone tells you "you were 3 cm too far left and 1 cm too high"
- **Optimizer** = you adjust your next throw slightly based on that feedback
- **Epoch** = one round of throwing at every target
- **Patience** = if your best score hasn't improved for 8 rounds, stop practicing

---

## 9. The 90th Percentile Safety Margin — What does it mean?

### The problem it solves

The GNN sometimes **underpredicts** traffic. If it says "the next bin will be 5 Mbps" but it's actually 7 Mbps, the planner reserved capacity for 5 and the link gets overloaded.

### How we compute the margin

After training, we run the model on all 780 **validation** windows and look at every case where it underpredicted:

```
For each validation window, for each active pair, for each horizon:
    underprediction = max(actual - predicted, 0)
    (if prediction was too HIGH, this is 0 — overprediction is fine, no danger)
```

Now we have thousands of underprediction values. We take the **90th percentile**:

```
Example underprediction values (sorted):
[0, 0, 0, 0.01, 0.02, 0.05, 0.08, 0.1, 0.15, 0.2, 0.25, 0.3, 0.5, 0.8, 1.2]
                                                            ↑
                                                     90th percentile ≈ 0.3
```

**90th percentile means:** 90% of the time, the model underpredicts by LESS than 0.3 Mbps. Only 10% of the time is the underprediction worse than this.

### How it's used

The planner adds this margin to every forecast before checking capacity:

```
WITHOUT margin:  "GNN says 5 Mbps → reserve 5 Mbps on links"
WITH margin:     "GNN says 5 Mbps → reserve 5 + 0.3 = 5.3 Mbps on links"
```

This makes the planner **conservative** — it assumes demand could be up to 0.3 Mbps higher than predicted. The trade-off:
- ✅ **Fewer surprises** — links are less likely to overload
- ❌ **Misses some green routes** — the buffer makes some paths look "too full" when they'd actually be fine

> [!NOTE]
> **Why 90th and not 100th?** The 100th percentile would be the worst-ever underprediction — so extreme it would make the planner TOO conservative and never pick greener routes. 90% coverage is a practical balance.

---

## 10. What does "Persistence" mean here?

### The simplest possible "prediction"

Persistence means: **"whatever happened last will happen next."**

```
Traffic at 12:00 PM was 5.2 Mbps for Italy→Netherlands

Persistence prediction:
  12:15 PM = 5.2 Mbps  (same as last observation)
  12:30 PM = 5.2 Mbps  (same)
  12:45 PM = 5.2 Mbps  (same)
```

No neural network, no learning, no parameters. Just **copy the last value**.

### Why include it?

Persistence is a **baseline** — the simplest thing that could possibly work. If the GNN can't beat persistence, then the GNN isn't contributing anything useful. It's like a benchmark: "is the fancy AI actually better than just assuming nothing changes?"

### The embarrassing result

In this project, persistence + the same safety margin achieves **the same overload reduction** (114 min/day) as the GNN + safety margin. This means the **safeguards** (margin, reservations, hysteresis) are doing the heavy lifting, not the GNN's ability to predict. The project honestly reports this.

---

## 11. Explain the Routing Algorithm Simply

Let me walk through **one time step** with a concrete example.

### Setup

- It's bin `k` (say, 10:00 AM)
- We have 6 OD pairs, each with 2–3 candidate paths
- Carbon intensities right now: France = 80, Germany = 350, Italy = 300, etc.

### Step 1: OBSERVE

The planner looks at traffic history through **bin k-1** (9:45 AM). It does NOT know what 10:00 AM traffic will be.

### Step 2: PREDICT

The GNN eats the last 12 bins (7:00–9:45 AM) and outputs predictions for 10:00, 10:15, and 10:30 AM.

```
GNN says for Italy→Netherlands:
  10:00 AM: 4.2 Mbps
  10:15 AM: 4.5 Mbps
  10:30 AM: 4.8 Mbps

Add safety margin (+0.3 Mbps):
  10:00 AM: 4.5 Mbps  ← planner uses these conservative numbers
  10:15 AM: 4.8 Mbps
  10:30 AM: 5.1 Mbps
```

### Step 3: SORT PAIRS BY DEMAND

The pair with the **highest conservative predicted demand** gets processed first. Why? Because the biggest flows have the most impact on link loads.

```
Order: Italy→NL (5.1), Italy→FR (4.3), NL→IT (3.8), DE→BE (2.1), ...
```

### Step 4: FOR EACH PAIR, EVALUATE CANDIDATES

**Processing Italy→Netherlands (the biggest flow):**

```
Current route: Italy → Germany → Netherlands
                        ↑ Germany has CI = 350 (dirty!)

Candidate A: Italy → Germany → Netherlands
  Carbon cost: 300 (Italy) + 350 (Germany) = 650
  Link loads after adding this flow: Germany→NL at 72% ✅ (under 80%)

Candidate B: Italy → Switzerland → France → Belgium → Netherlands
  Carbon cost: 300 + 90 + 80 + 120 = 590  ← LOWER (greener!)
  Link loads: Switzerland→France at 83% ❌ (over 80% limit!)
  → INFEASIBLE (rejected)

Candidate C: Italy → Germany → Belgium → Netherlands
  Carbon cost: 300 + 350 + 120 = 770
  Link loads: all under 80% ✅ but more expensive

Winner: Candidate A (only feasible one with lowest carbon cost)
```

### Step 5: APPLY HYSTERESIS

Before switching, check:
- Is the new path ≥ 5% better? If Italy→NL was already on path A, no change needed.
- Has it been ≥ 2 bins since last change? If we just switched 15 min ago, hold.
- **Exception:** If the current path is at capacity risk (links near overload), switch anyway!

### Step 6: UPDATE RESERVATIONS

After deciding Italy→NL's path, **immediately add** its reserved capacity to the projected link loads. Now when we evaluate the NEXT pair (Italy→France), it sees the updated loads including Italy→NL's reservation.

This is the **shared reservation** mechanism — it prevents two pairs from both thinking the same link has room.

### Step 7: REVEAL ACTUAL DEMAND

Only NOW does the simulation reveal the real 10:00 AM traffic. Maybe it was 4.8 Mbps for Italy→NL, not 4.2 as predicted.

### Step 8: COMPUTE SERVED RATES

Run progressive filling: if any link is overloaded, fairly reduce all flows sharing that link.

### Step 9: LOG EVERYTHING

Record offered demand, served rates, link utilizations, carbon score, route changes, etc.

### Step 10: ADVANCE TO NEXT BIN (10:15 AM) AND REPEAT

### Visual summary of one step:

```
9:45 AM data ──→ GNN predicts ──→ Add margin ──→ Sort pairs by demand
                                                        │
                    ┌───────────────────────────────────┘
                    │
                    v
        For each pair (biggest first):
        ┌─────────────────────────────────────────┐
        │ 1. Remove old reservation               │
        │ 2. Test each candidate path:             │
        │    - Links > 80%? → reject               │
        │    - Carbon cost = Σ(CI at each hop)     │
        │ 3. Pick best feasible (lowest carbon)    │
        │ 4. Check hysteresis (5% + 2-bin hold)    │
        │ 5. Add new reservation                   │
        └─────────────────┬───────────────────────┘
                          │
                          v
              All pairs decided → routes locked
                          │
                          v
              Reveal actual 10:00 AM traffic
                          │
                          v
              Progressive fill → served rates
                          │
                          v
              Record metrics → next bin
```

---

## Quick Reference Card

| Term | One-line explanation |
|------|---------------------|
| **GNN** | Neural network that uses graph connections (who's neighbors with whom) |
| **GCN** | A specific type of GNN layer: average your neighbors' features |
| **GRU** | Neural network for time sequences: reads history, produces a memory |
| **Hysteresis** | "Don't switch routes unless it's clearly worth it" |
| **Candidate paths** | The 2–3 possible routes for each source→destination pair |
| **Active OD pairs** | The 6 (out of 56) origin-destination flows we actually simulate |
| **Chronological split** | Train on past, validate on middle, test on future — no time travel |
| **Parameters** | The 7,672 adjustable numbers inside the neural network |
| **Epoch** | One full pass through all training data |
| **Loss (MAE)** | Average prediction error in Mbps — the number we minimize |
| **Seed** | Fixed random starting point for reproducibility |
| **90th percentile margin** | "90% of the time, the model underpredicts by less than this" |
| **Persistence** | Simplest baseline: "next bin = same as last bin" |
| **Shared reservations** | After choosing a path, immediately reserve its capacity |
| **Progressive filling** | Fair max-min rate allocation when links are overloaded |
