# What limited the order?

On election night I initially suspected that small result-following orders meant the system was late or the book was thin. In a review of recorded opportunities, the size offered at the decision price sometimes exceeded what the strategy could buy under its spending rules. Holding the sequence of opportunities fixed let me test that explanation.

This public experiment uses four clockwork animals undergoing acceptance trials at an imaginary museum. The story, times, prices, sizes and budgets were written for this example. Each local contract pays one credit if its animal passes its trial. A museum inspector reports each pass before the strategy decides whether to buy. The local contract settles later.

```sh
python3 -m marketlab.replay
python3 -m unittest discover -s tests -p 'test_replay.py' -v
```

## What the strategy knew

Times are seconds on a single clock. Each ask is written as price × shares. The two books in a row describe the same batch of offers. Each subsequent row brings a fresh batch.

| Trial | Pass received | Decision | Asks at decision | Order arrival | Asks at arrival |
| --- | ---: | ---: | --- | ---: | --- |
| Heron | 4 | 7 | 0.73 × 11 | 10 | Empty |
| Otter | 14 | 18 | 0.68 × 9, 0.82 × 17 | 21 | Unchanged |
| Lynx | 24 | 31 | 0.78 × 19 | 34 | Unchanged |
| Marten | 41 | 47 | 0.85 × 3, 0.91 × 12 | 50 | Unchanged |

Every run starts with 31 cash credits and keeps 4 in reserve. Each buy has a fixed limit of 0.88 and costs an additional 0.02 per share filled. At the decision time, a received pass for that trial permits an order. The strategy takes the smallest of the remaining total allowance, the remaining allowance for that trial and the available cash above the reserve. It sets aside 0.90 per requested share and also limits the request to the quantity displayed at eligible prices.

Three seconds later the model walks the arrival book from the cheapest ask up to the fixed limit and requested size. Any remainder expires immediately. The cost of each modeled fill, including fees, consumes both allowances. Unspent cash becomes available for the next decision. The wallet receives no settlement proceeds during the experiment.

## Two limits, four outcomes

Each row replays the same events in order from the same cash balance. The final column assumes that every hypothetical purchase shown in the table eventually pays one.

| Total cap | Per-trial cap | Shares at arrival (Heron / Otter / Lynx / Marten) | Total debit | Conditional net |
| ---: | ---: | --- | ---: | ---: |
| 11 | 6 | 0 / 6 / 6 / 2 | 10.74 | 3.26 |
| 28 | 6 | 0 / 6 / 6 / 3 | 11.61 | 3.39 |
| 11 | 14 | 0 / 12 / 2 / 0 | 10.42 | 3.58 |
| 28 | 14 | 0 / 15 / 15 / 3 | 25.95 | 7.05 |

For Otter, a per-trial allowance of 6 can reserve six shares. Those six cost 4.20 including fees. Increasing the total cap alone leaves that order unchanged. Increasing the per-trial cap alone gives Otter more of a limited budget. The 11-credit total then leaves only two affordable shares for Lynx. Raising both caps funds larger orders on both trials. Marten still offers only three eligible shares at arrival.

Heron provides a control for timing. With caps of 28 and 14, the decision book supports a request for eleven shares. In the zero-delay comparison the same request reaches that book immediately and the modeled size is eleven. After three seconds it reaches an empty book and the size is zero under all four policies.

The experiment measures sensitivity to the two caps and one change in timing on a fixed sequence. Displayed quantities stand in for fills at arrival. Queue priority, market impact and new opportunities that larger orders could create or displace fall outside this model. Conditional net also depends on local settlement. The inspector's report alone cannot establish that payment.
