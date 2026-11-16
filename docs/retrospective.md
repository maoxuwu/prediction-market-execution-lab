# From passive quotes to event-driven execution

My initial question in the Susquehanna Predictions Cup was whether a small automated trader could capture a displayed spread. I started with passive quotes on a simulated exchange and ended up spending much more time on three questions: what counted as a fill, which claims really offset each other, and what information was available when an order could actually reach the book.

## A print at my price

A passive order can be resting while someone else trades at a compatible price. The matching queue can put other orders ahead of mine. I kept quote acknowledgements, terminal order states and confirmed fills separate, then compared the time my quotes were resting with public activity. That changed the question from “was there a spread?” to “what evidence shows my order earned it?” Without queue-position evidence, the defensible answer for an expired, unfilled order is zero executed size.

## Buying the other side

Moving to paired trades made the cost of an incomplete order visible. It matters whether the two contracts cover every allowed outcome, whether both legs fit in the same wallet, and whether the second book still exists after the first fill. Two party-labelled election contracts can have different settlement criteria. I checked their written rules before treating any relationship as a hedge. In the [worked example](../README.md#run-the-experiment), the payout is deliberately simpler so that changing just the second book isolates execution risk.

I measured inventory in units from the date of entry. A long-held unit that had never sold still occupied capital. Dropping it from the sample would make the apparent turnover faster. Recording normal exits, repairs and unsold inventory separately made this visible. I kept time spent offline in elapsed holding time because capital remained tied up throughout.

## What changed on election night

I compared external forecasts, market references and result reports with the exchange's own contract definitions and available depth. The important timestamp was when a specific version reached the strategy. An earlier timestamp inside a report tells a different story if the report arrived after the quote moved. Revised totals also needed their own history. I treated a second download of the same release as a repeated observation.

I initially thought small purchases meant that the quote had moved or too little was left to buy. Replaying a result-following entry changed my view. I used the local book received just before the order. At the best price it still offered several times the quantity purchased, and the account had cash available. The spending limit for that race set the order size. Later entries also drew on a cumulative strategy budget. Holding the sequence of books fixed and varying each limit separately showed how raising one limit could leave the other binding.

Other decisions faced different constraints. On an external price move, the local ask could already have moved beyond the rule's entry price by the time of confirmation. When I examined how much of a large directional holding I could close, the first price level covered only a fraction of it. An early exit also gave up a possible settlement payment. The account had enough cash for the purchases that followed at their observed prices and sizes even without the proceeds from those exits.

One change that affected actual entries was separating an external outcome report from a tradable quote. An external venue could settle a market and stop quoting while a matching local contract still traded. An early filter discarded the result along with the empty quote. The revised entry rule checked that the result referred to the same proposition, then read the local book. For exits from result-following inventory the system separately checked the cost of the FIFO inventory and allowed for a fee before placing the offset.

## What I would test next

The first budget replay used the books for entries that actually traded. I would extend it to rejected candidates, keeping them in receipt order and giving every rule the same wallet. I would record whether there was a sufficient book, a fully observed empty book, or no book at the decision time. Only the first two observations support a numerical size comparison.

For the repricing rule I would compare confirmation delays on a held-out set of events. That requires a book at each proposed decision time. I would report how often such a book exists and how much the wallet could buy at its displayed prices. Where an intermediate book is missing, a later price cannot establish what an earlier order could have bought.

The competition system used persistent order records and account reconciliation to operate in a simulated venue. This public edition reconstructs selected methods with fictional inputs. It provides exercises and reproducible tests for the methods. The competition account, historical market feed, operational service and participant portfolios remain outside the repository. [Competition rules, section 14](https://predictionscup.com/rules/)
