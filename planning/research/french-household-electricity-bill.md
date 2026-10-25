# How a French household electricity bill is composed

Research note, 2026-10-25. Scope: households, low voltage ≤ 36 kVA (BT ≤ 36 kVA), mainland France.
Every figure carries its source and effective date, and a status:

- **official**: read in the regulator's or network operator's own publication;
- **to verify**: from secondary sources only; must be checked against the official text before it
  is used in a rate table.

Rates change several times a year (February and August for most of them), so **every value in
the model has an effective period**.

## 1. The stack

A bill is built in layers. Each layer has its own basis, payee and legal source.

| Layer | What it pays for | Basis | Payee | Legal / tariff source |
|---|---|---|---|---|
| **Supply** (fourniture) | energy, capacity, supplier costs and margin | fixed €/month + €/kWh (by tariff option) | supplier | regulated tariff (TRVE, set by the government on a CRE proposal) or market offer |
| **Network** (TURPE, acheminement) | distribution and transmission networks | fixed (management, metering, € per kVA) + €/kWh by time class | Enedis (and RTE), via the supplier | CRE deliberation, TURPE 7 HTA-BT |
| **CTA** (contribution tarifaire d'acheminement) | pensions of the electricity and gas industries (CNIEG) | **% of the fixed part of TURPE** | CNIEG | ministerial order |
| **Accise sur l'électricité** (ex-TICFE/CSPE, now including the former local TCFE) | public service charges, budget | €/MWh consumed | State | Code des impositions sur les biens et services (CIBS) |
| **VAT** (TVA) | — | % of all the above | State | CGI |

For a regulated-tariff (Tarif Bleu) customer, supply and TURPE are **not shown separately**: the
TRVE is built by "stacking" (empilement) and already includes TURPE. The bill shows a subscription
and a kWh price (taxes excluded), then CTA, accise and VAT. Reconstructing TURPE from the official
grid is therefore what decomposing a bill means (§5).

## 2. TURPE 7 for BT ≤ 36 kVA — **official**, in force since 2026-08-01

Source: Enedis, *Tarifs d'utilisation des réseaux publics d'électricité au 01/08/2026, TURPE 7
HTA/BT* (https://www.enedis.fr/media/4717/download), pp. 17–19, implementing CRE deliberation
n° 2026-105 of 2026-05-21 (+3.04 % on 2026-08-01). All prices exclude taxes.

Annual network charge for one connection point: **CG + CC + CS** (+ CACNC without a smart meter).

**Management component (CG), €/year**, depends on the contract and the user's status:

| Status | Contract unique (normal household) | CARD |
|---|---|---|
| Consumer, or self-producer **without** injection | 17.12 | 18.39 |
| Participant in **collective** self-consumption | 21.75 | 23.02 |
| Self-producer **with** injection | 26.95 | — |

**Metering component (CC)**: 22.67 €/year (smart meter, bimonthly transmission or more often).
Without a meter: 1.80 €/year. **CACNC** (no smart meter, refusal): 6.68 €/2 months, plus
4.27 €/2 months if the last real reading is older than 12 months.

**Withdrawal component (CS) = b × P + Σᵢ cᵢ × Eᵢ**, where P is the subscribed power (kVA) and Eᵢ
the energy withdrawn in time class i (kWh). The supplier chooses the *formule tarifaire
d'acheminement* (FTA) per connection:

| FTA | b (€/kVA/year) | HPH | HCH | HPB | HCB (c€/kWh) |
|---|---|---|---|---|---|
| CU4 (short use, 4 classes) | 10.42 | 7.72 | 4.09 | 1.71 | 1.20 |
| MU4 (medium use, 4 classes) | 12.49 | 7.21 | 3.84 | 1.66 | 1.14 |
| LU (long use, flat) | 95.96 | 1.29 | 1.29 | 1.29 | 1.29 |
| CU (flat, derogatory, no smart meter) | 11.41 | 4.99 | 4.99 | 4.99 | 4.99 |
| MUDT (2 classes, derogatory) | 13.90 | 5.09 | 3.61 | 5.09 | 3.61 |

**Collective self-consumption**, all participants downstream of the same HTA/BT substation, may
choose an FTA that bills energy coming from the operation (*autoproduite*) differently from energy
coming from the grid (*alloproduite*); b is unchanged (10.42 CU4, 12.49 MU4):

| FTA | part | HPH | HCH | HPB | HCB (c€/kWh) |
|---|---|---|---|---|---|
| CU4 collective | alloproduite (from the grid) | 7.75 | 4.15 | 1.78 | 1.25 |
| CU4 collective | **autoproduite** (from the operation) | **2.95** | **1.32** | **0.78** | **0.50** |
| MU4 collective | alloproduite | 7.25 | 3.87 | 1.66 | 1.18 |
| MU4 collective | **autoproduite** | **2.68** | **1.27** | **0.77** | **0.50** |

**Time classes.** High season (saison haute) = November to March inclusive; low season = April to
October inclusive (grid p. 7). Peak/off-peak hours (HP/HC) are **specific to each connection
point** (8 hours of HC per day, set by Enedis): they are an input of the contract, not a national
constant.

**Injection component (CI)**: **zero** for BT and HTA (grid p. 8). Injecting costs no
per-kWh network charge; it changes the management component (26.95 instead of 17.12 €/year).

## 3. Taxes — **official** (energie-info.fr, the national energy ombudsman's site)

Source: https://www.energie-info.fr/fiche_pratique/cspe-ticgn-cta-tva-toutes-les-taxes-sur-ma-facture/

| Tax | Value | Effective from | Base |
|---|---|---|---|
| Accise (households ≤ 36 kVA) | 30.85 €/MWh | 2026-02-01 | kWh consumed from the grid |
| Accise (households ≤ 36 kVA) | **30.62 €/MWh** | **2026-08-01** | idem |
| CTA (distribution) | 21.93 % | until 2026-01-31 | fixed part of TURPE |
| CTA (distribution) | **15 %** | **2026-02-01** (order of 2026-01-28) | fixed part of TURPE |
| VAT | 5.5 % on subscription and CTA, 20 % on the rest | until 2025-07-31 | — |
| VAT | **20 % on everything** (subscription, consumption, accise, CTA) | **2025-08-01** | — |

VAT applies **on top of** CTA and accise (tax on tax).

**Exemptions** (to verify in the CIBS text before encoding):

- Electricity **produced and consumed on site** (individual self-consumption) is not withdrawn
  from the grid: it pays no supply, no TURPE energy part, no accise, no VAT.
- **Collective self-consumption**: a zero accise rate (0 €/MWh) since 2025-03-01 for the
  electricity shared within an operation, if renewable and the plant is below 1 MW (Finance Act
  2025, art. 75, amending CIBS L. 312-79 and L. 312-87). The tax administration's restrictive
  commentary (a direct physical connection) was withdrawn from the BOFiP on 2026-05-13.
  Sources: [Seban Avocats](https://www.seban-associes.avocat.fr/accise-sur-lelectricite-confirmation-de-la-dispense-en-autoconsommation-collective-etendue/),
  [pv magazine](https://www.pv-magazine.fr/2025/02/11/lautoconsommation-collective-exoneree-daccise-jusqua-1-mw/).

## 4. Selling — **to verify**

- **Surplus sold to the grid** (obligation d'achat, EDF OA, ≤ 9 kWc): 4 c€/kWh until
  2026-06-04; about **1.1 c€/kWh** under the S21 order of 2026-06-04; the self-consumption
  investment premium was abolished on 2026-06-05. Sources: secondary
  ([potentielsolaire](https://www.potentielsolaire.com/prix-rachat-electricite-photovoltaique),
  [selectra](https://selectra.info/energie/solaire/autoconsommation-prime)). Must be checked
  against the order in the Journal officiel.
- **Selling to a neighbour** is done through a collective self-consumption operation (PMO): the
  price is set by the operation's agreement, the neighbour pays the *autoproduite* TURPE (§2) and
  zero accise (§3) on that energy, and buys the rest from their supplier. VAT on the PMO price,
  and income-tax treatment of household sales, are **open questions**.

## 5. Regulated tariff (Tarif Bleu) — **to verify**

Secondary sources report, for 2026-08-01 (CRE deliberation n° 2026-147 of 2026-07-15),
6 kVA, VAT included: Base 0.2001 €/kWh; HP/HC 0.2142 / 0.1589 €/kWh; subscription 190.32 €/year
([fournisseurs-electricite.com](https://www.fournisseurs-electricite.com/fournisseurs/edf/tarifs/bleu-reglemente)).
To be read from the CRE deliberation before use.

## 6. Consequences for the model

1. **Rates are dated data, not code.** Each value has a source, an effective period and a status;
   the February/August cadence makes this unavoidable.
2. **Charges attach to energy flows**, not to "consumption" in general. The same kWh costs
   differently when it is:
   - taken from the grid: supply + TURPE energy (by time class) + accise + VAT;
   - self-consumed on site: nothing;
   - received from a collective operation: PMO price + *autoproduite* TURPE + zero accise (+ VAT?);
   - injected to the grid: earns the OA price, with no per-kWh network charge.

   With the values above, a kWh avoided at peak time saves about 0.20 €, while a kWh exported earns
   about 0.011 €, a ratio of about 18. This asymmetry is exactly what the optimisation must see.
3. **Fixed parts depend on the contract** (subscribed kVA, FTA, status: consumer, collective
   participant, producer with injection). Becoming a producer with injection changes a fixed
   charge, which is a real cost of selling.
4. **Time classes need two calendars**: the national season (November–March) and the
   connection's own HP/HC hours.
5. **Companies** differ only by data and by more components (BT > 36 kVA and HTA grids,
   reduced-power overrun charges, reduced accise rates for some uses), so the same structure
   extends to them.

## 7. Open questions

Recorded on 2026-10-25, to settle before modelling sales to neighbours (M7):

1. **VAT on the price of energy sold within a collective self-consumption operation**: who is
   liable (the producer, the PMO), at which rate, and does a household seller fall under the VAT
   franchise threshold?
2. **Income tax on household sales** (to the grid under OA, and within an operation): exemption
   thresholds (e.g. installations ≤ 3 kWc) and how they apply to collective sales.
3. **Surplus feed-in price after 2026-06-04**: read the S21 order in the Journal officiel and
   confirm the ~1.1 c€/kWh value (§4).
4. **Tarif Bleu 2026-08-01**: read CRE deliberation n° 2026-147 (§5).
5. **Which FTA a regulated-tariff supplier applies** to a Base or HP/HC household (CU4 or MU4); the
   inverse decomposition depends on it.
