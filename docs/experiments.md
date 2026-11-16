# Measurement and settlement assumptions

## Revisions and look-ahead

Suppose a report about whether a measure *passes* is published at second 25 and first received at 28. A corrected version of that publication arrives at 44. A separate report concerns whether the measure *takes effect*. Someone entering at second 40 could use the original report about passage. Attributing the correction to that decision would leak information acquired four seconds later. The other proposition has a different payoff even if both refer to the same measure.

The [as-of query](../marketlab/evidence.py) uses integer elapsed seconds on a common timeline, one source per stream, exact proposition identity and a maximum source age. Re-reading an old release cannot extend its age. Conflicting values for the same visible publication and version raise an error. Run `python3 -m unittest discover -s tests -p 'test_evidence.py' -v` to inspect these cases. Source timestamps in the examples are comparable by construction. A real feed also needs clock and identity validation.

## The denominator in an exit rate

Consider two mature lots of six and four units and a young lot of two. With a ten-second horizon, six of the ten mature units exited normally within the horizon, one was closed by a repair and three were still held at their respective deadlines. The normal-exit fraction is **6/10**. A later normal sale can improve cash today while leaving yesterday's within-horizon statistic unchanged. The two young units can enter the denominator once their entire window has elapsed.

The [cohort tests](../tests/test_cohorts.py) exercise FIFO attribution, eligibility at the deadline and partial exits. A unit-weighted fraction answers a turnover question. An order-weighted fraction or the median age of completed trades would answer a different one.

## When the reply goes missing

An order is saved, the process starts a submission and the acknowledgement never arrives. The wallet might already hold the shares. Run `python3 -m marketlab.recovery_demo` to see the [journal](../marketlab/journal.py) reopen and evaluate fictional account records.

The exercise follows a single buy in a wallet that starts with no opposite-side inventory. Cash, prices and fees are in integer cents. The journal records the requested terms and opening balance as `PREPARED`. Before an order could leave, one caller must commit a transition to `POSSIBLY_SENT`. A crash on either side of the outbound call can leave that same state. Recovery can check evidence repeatedly without sending another order.

| Evidence available after restart | Journal outcome |
| --- | --- |
| A unique terminal order matches the original terms and time window. Its fills, fees, cash change and share change reconcile. | `MATCHED_ORDER`. A terminal partial fill accounts for the quantity that actually traded. |
| Complete order and fill histories cover the submission through a closing observation after expiry. There is no order or fill in that window and cash and shares agree with the opening balance. | `NO_EFFECT`. The original submission remains consumed. |
| History is incomplete, two records fit, a matching order is still open, or the wallet disagrees with the fills. | `POSSIBLY_SENT`. The journal keeps the original intent unresolved. |

The supplied history stands in for final order and trade pages from the venue. The caller supplies their coverage and an independently observed closing balance. Cash and holdings can return to their starting values after intervening trades, so identical balances alone cannot establish an empty history. The code and examples use local records throughout.

The [FIFO account example](../marketlab/ledger.py) starts one step later, from verified fills. A partially matched buy can both close old lots and open a new one. Each side's actual fill fee is allocated to the matched or remaining units. After every event, cash plus remaining acquisition cost equals initial capital plus realised P&L. A market-value estimate would also include the unrealised gain or loss on current inventory.

## When two NOs are a hedge

Suppose two separate contracts ask whether organisation A and organisation B win an award. Buy one NO on each. The hypothetical payout matrix follows directly from the two written contracts.

| Settlement state | A NO pays | B NO pays | Total payout |
| --- | ---: | ---: | ---: |
| A alone wins | 0 | 1 | 1 |
| B alone wins | 1 | 0 | 1 |
| Neither wins | 1 | 1 | 2 |
| Both win | 0 | 0 | 0 |

If the award permits joint winners, the last row belongs in the analysis. A package price of 0.90 can still lose its full cost. If the terms exclude joint winners and both orders fill, the same package has a minimum payout of 1 before fees. If only the first order fills, the paired floor no longer applies. Settlement compatibility and execution completeness are separate requirements.
