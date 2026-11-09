# Measurement and settlement assumptions

## Revisions and look-ahead

Suppose a report about whether a measure *passes* is published at second 25 and first received at 28. A corrected version of that publication arrives at 44. A separate report concerns whether the measure *takes effect*. Someone entering at second 40 could use the original report about passage. Attributing the correction to that decision would leak information acquired four seconds later. The other proposition has a different payoff even if both refer to the same measure.

The [as-of query](../marketlab/evidence.py) uses integer elapsed seconds on a common timeline, one source per stream, exact proposition identity and a maximum source age. Re-reading an old release cannot extend its age. Conflicting values for the same visible publication and version raise an error. Run `python3 -m unittest discover -s tests -p 'test_evidence.py' -v` to inspect these cases. Source timestamps in the examples are comparable by construction. A real feed also needs clock and identity validation.

## The denominator in an exit rate

Consider two mature lots of six and four units and a young lot of two. With a ten-second horizon, six of the ten mature units exited normally within the horizon, one was closed by a repair and three were still held at their respective deadlines. The normal-exit fraction is **6/10**. A later normal sale can improve cash today while leaving yesterday's within-horizon statistic unchanged. The two young units can enter the denominator once their entire window has elapsed.

The [cohort tests](../tests/test_cohorts.py) exercise FIFO attribution, eligibility at the deadline and partial exits. A unit-weighted fraction answers a turnover question. An order-weighted fraction or the median age of completed trades would answer a different one.

## When the reply goes missing

Imagine an intent is saved, a request could have reached the venue, and the process stops before recording the reply. A new process inherits the unresolved intent. The [SQLite example](../marketlab/journal.py) stores the claim before any hypothetical send. It gives only one caller permission to attempt that immutable intent. A terminal receipt closes the record after independent verification. If no evidence arrives, the intent stays unresolved. This sacrifices possible execution to prevent duplicate exposure.

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
