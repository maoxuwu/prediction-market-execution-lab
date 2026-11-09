# Prediction Market Execution Lab

Can a quoted spread survive the time it takes to buy both legs? In the worked example, a wallet can afford five complementary pairs for **4.48**. The first order fills, then liquidity on the second leg shrinks. The ledger shows **+0.22 realised**, while the remaining position can still take the trade to **−0.89** at settlement.

I built and operated a Python trading system as an individual participant in the **2026 Susquehanna Predictions Cup**, a simulated competition. It began with passive quoting and grew to include sequential paired orders, event-driven signals and a reconciled inventory ledger. This repository is an independently implemented, offline companion to that project. All prices, events and fills distributed here are invented for the examples. [Project retrospective](docs/retrospective.md) · [Official competition](https://predictionscup.com/rules/)

## Run the experiment

From the repository root, using Python 3.10 or later and its standard library:

```sh
python3 -m marketlab.demo
python3 -m marketlab.demo --second-leg-depth 0
python3 -m marketlab.demo --second-leg-depth 5
python3 -m unittest discover -s tests -v
```

The wallet starts with 12 units, each winning share pays 1, and each purchase costs an additional 0.01 per share. Both sides of **one** binary proposition are available. The first order buys five YES shares at 0.36. Change the available size at 0.51 before the NO order arrives to see where the return comes from.

| Second-leg depth | Residual holding | Realised P&L after offsets | Total P&L if YES wins | Total P&L if NO wins |
| ---: | --- | ---: | ---: | ---: |
| 0 | 5 YES | 0.00 | +3.15 | −1.85 |
| 2 | 3 YES | +0.22 | +2.11 | −0.89 |
| 5 | Flat | +0.55 | +0.55 | +0.55 |

At depth two, two pairs redeem for 2. Their acquisition cost, including fees, was 1.78. Three YES shares still have a FIFO cost of 1.11. This is why the 2 credited to the wallet produces only 0.22 of realised profit. The five-share case improves on the original plan because all five NO shares become available at 0.51.

## Questions you can reproduce

| Question | Implementation | What to look for |
| --- | --- | --- |
| How much fits inside one wallet? | [Depth and sizing](marketlab/depth.py) | Walk each ask level, charge both fees, and stop at the marginal pair-cost limit. |
| What was known when a decision was made? | [Point-in-time evidence](marketlab/evidence.py) | Match the exact proposition and use the time each version was actually received. |
| What survives a process restart? | [SQLite intent journal](marketlab/journal.py) | A claimed action stays unresolved until a verified terminal receipt is supplied. |
| Which part of an offset is income? | [FIFO ledger](marketlab/ledger.py) | Allocate fees across partial fills and reconcile cash, remaining cost and realised P&L. |
| How often did inventory exit within a deadline? | [Cohort analysis](marketlab/cohorts.py) | Track partial exits against original entry units and show how much inventory has had a full observation window. |

The journal and fill ledger are separate teaching components. The caller provides verified fills in execution order. The examples assume immediate unit redemption for opposite sides of the same contract. Cross-contract trades require their own outcome-by-outcome payout analysis. [Model assumptions and research examples](docs/experiments.md)
