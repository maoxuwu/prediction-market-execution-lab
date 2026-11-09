# From passive quotes to event-driven execution

My initial question in the Susquehanna Predictions Cup was whether a small automated trader could capture a displayed spread. I started with passive quotes on a simulated exchange and ended up spending much more time on three questions: what counted as a fill, which claims really offset each other, and what information was available when an order could actually reach the book.

## A print at my price

A passive order can be resting while someone else trades at a compatible price. The matching queue can put other orders ahead of mine. I kept quote acknowledgements, terminal order states and confirmed fills separate, then compared the time my quotes were resting with public activity. That changed the question from “was there a spread?” to “what evidence shows my order earned it?” Without queue-position evidence, the defensible answer for an expired, unfilled order is zero executed size.

## Buying the other side

Moving to paired trades made the cost of an incomplete order visible. It matters whether the two contracts cover every allowed outcome, whether both legs fit in the same wallet, and whether the second book still exists after the first fill. Two party-labelled election contracts can have different settlement criteria. I checked their written rules before treating any relationship as a hedge. In the [worked example](../README.md#run-the-experiment), the payout is deliberately simpler so that changing just the second book isolates execution risk.

I measured inventory in units from the date of entry. A long-held unit that had never sold still occupied capital. Dropping it from the sample would make the apparent turnover faster. Recording normal exits, repairs and unsold inventory separately made this visible. I kept time spent offline in elapsed holding time because capital remained tied up throughout.

## What changed on election night

I compared external forecasts, market references and result reports with the exchange's own contract definitions and available depth. The important timestamp was when a specific version reached the strategy. An earlier timestamp inside a report tells a different story if the report arrived after the quote moved. Revised totals also needed their own history. I treated a second download of the same release as a repeated observation.

A correct directional view could still be unattractive to buy. A runner quoted near its payout ceiling offered little upside per unit, and the size available at the top price could be much smaller than the desired position. Exiting existing inventory had its own cost: it freed cash immediately and gave up a possible settlement payout. I compared that trade-off with specific reinvestment opportunities.

One practical improvement came from separating an outcome report from an executable quote. A resolved external market could stop quoting while the contract I owned still traded on the competition venue. An early filter discarded both pieces of information together. The revised system checked the result against the same proposition, read fresh local depth, and priced an offset against the actual FIFO lots and a fee allowance. That gave the exit rule an explicit economic test at the point of execution.

## What I would test next

I would record the first eligible event, the first book observed after it, the confirmation time and the first executable book after confirmation. On a held-out set of events, I would compare otherwise identical rules with shorter and longer confirmation delays. For each rule I would report the share of events with observable depth, the quantity the wallet could fund and the inventory remaining after the second order. This would make it possible to separate delay from missing liquidity. Where the intermediate book was never observed, the counterfactual return would remain unknown.

The competition system used persistent order records and account reconciliation to operate in a simulated venue. This public edition reconstructs selected methods with fictional inputs. It provides exercises and reproducible tests for the methods. The competition account, historical market feed, operational service and participant portfolios remain outside the repository. [Competition rules, section 14](https://predictionscup.com/rules/)
