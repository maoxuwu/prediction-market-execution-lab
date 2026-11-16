# Prediction Market Execution Lab

[![Offline tests](https://github.com/maoxuwu/prediction-market-execution-lab/actions/workflows/tests.yml/badge.svg)](https://github.com/maoxuwu/prediction-market-execution-lab/actions/workflows/tests.yml)

When a trading rule buys very little, did the order arrive late, did the book run out, or did the rule itself stop buying? In the **2026 Susquehanna Predictions Cup**, I initially suspected timing and liquidity. Replaying a result-following trade showed that the best price still had ample size in the last book observed before submission. My limit on spending in one race had set the quantity.

I entered the simulated competition as an individual. I set the strategy objectives and risk limits, used AI coding agents to implement and monitor the system, and reviewed the resulting trades. I put together this offline lab after the competition so readers can run selected experiments with independently invented inputs. [Project retrospective](docs/retrospective.md) · [Official competition](https://predictionscup.com/rules/)

**Start with the [budget replay](docs/decision-replay.md).** Run `python3 -m marketlab.replay` to vary the spending limits on a fixed sequence of books. One example also lets you see what happens when the offer disappears before the order arrives.

| Competition phase | Question I investigated | Explore in the lab |
| --- | --- | --- |
| Passive quoting | How could I tell whether my resting order filled? | [A trade at my price](docs/retrospective.md#a-print-at-my-price) |
| Paired orders | What happens if the second order fills only partly? | [Change the second book](#run-the-experiment) |
| Inventory study | How much capital was still tied up at a fixed horizon? | [Choose the exit-rate denominator](docs/experiments.md#the-denominator-in-an-exit-rate) |
| Result-following orders | Which constraint determined the size I could buy? | [Replay the same books under four budget rules](docs/decision-replay.md) |

## Run the experiment

Five complementary pairs meet the all-in cost limit of 1 per pair, for a total planned cost of **4.48**. The sixth pair would cost 1.04 including fees. The first order fills, then the second book changes. Run the example with Python 3.10 or later and its standard library.

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

| Question | Competition system | Public example and its assumptions |
| --- | --- | --- |
| How much fits inside one wallet? | Two NO orders on separate contracts required compatible payout rules. The system could attempt a repair within a loss limit. | [Second-leg demo](marketlab/demo.py) buys YES and NO on one proposition. A partial fill leaves the remaining shares open. |
| What could the strategy know at decision time? | Each external report had a version, a receipt time and a contract to match. | [Point-in-time query](marketlab/evidence.py) uses a single stream with a shared clock. |
| How does an order survive a lost reply? | Recovery matched the original request to order history or checked for any account effect after expiry. | [SQLite journal](marketlab/journal.py) persists the intent and accepts a terminal receipt verified by its caller. |
| Which part of an offset is income? | The ledger reconciled actual quantities, costs and fees to the account. | [FIFO ledger](marketlab/ledger.py) takes verified fills as input and assumes unit redemption on a same-contract offset. |
| How often did inventory exit within a deadline? | The study followed each entry cohort, including unsold units, over a fixed window. | [Cohort analysis](marketlab/cohorts.py) distinguishes normal sales, repairs and units too young for the comparison. |

The journal and fill ledger are separate teaching components. The caller provides verified fills in execution order. The examples assume immediate unit redemption for opposite sides of the same contract. Cross-contract trades require their own outcome-by-outcome payout analysis. [Model assumptions and research examples](docs/experiments.md)
