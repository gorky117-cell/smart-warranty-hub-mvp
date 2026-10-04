# OEM registry review — 2026-10-04

Scope: `data/oem_domains.json` (200 entries), `data/oem_verified.json`, `data/oem_manual_confirmed.json`.
Nothing in section A has been changed; each row needs an owner decision. "Verified" = passed the
automated check in fix run 91.B8 (the domain belongs to *a* company with that name — not necessarily the
one that made the customer's product).

## A. Brand names shared by unrelated companies (for review)

| Registry name | Registry domains | Verified? | Unrelated companies using the name | Risk | Suggested action |
|---|---|---|---|---|---|
| Bajaj | bajaj.com, bajajauto.com | yes, both | Bajaj Electricals (fans, appliances), Bajaj Auto (two-wheelers), Bajaj Finserv (finance) — separate listed companies | A "Bajaj" fan invoice can accept Bajaj Auto terms | Drop `bajajauto.com` from `Bajaj`; resolve "Bajaj" by product category (appliance -> Bajaj Electricals, vehicle -> Bajaj Auto) |
| Bajaj Finserv | bajajfinserv.in | yes | Lender, not a product maker (shows on EMI invoices) | EMI line read as the brand | Remove from the OEM registry, or mark as non-OEM |
| Godrej | godrej.com | no | Godrej & Boyce / Godrej Enterprises (appliances, locks) vs Godrej Industries / Consumer Products (soaps) — group split in 2024 | Low today (not verified) | Point `Godrej` / `Godrej Appliances` at the appliances site after a check |
| Tata | tata.com, tatamotors.com | yes, both | Tata group holding site; Tata Motors (cars); Croma is Tata-owned retail | Group site holds no product terms | Keep `Tata Motors` only; treat bare "Tata" as ambiguous |
| Hero | heromotocorp.com | yes | Hero MotoCorp (motorcycles), Hero Cycles, Hero Electric (EV scooters) — unrelated | Hero Electric / Hero Cycles invoices get MotoCorp terms | Resolve by category; add Hero Electric / Hero Cycles separately if needed |
| Honda | honda.com, hondacarindia.com | yes, both | Honda Cars India vs Honda Motorcycle & Scooter India (separate site); honda.com is the US site | Two-wheeler invoices get car terms | Split into Honda Cars / Honda 2-wheelers |
| Usha / USHA | ushainternational.com | no | Usha International (fans, appliances) vs Usha Shriram (also sells appliances) vs Usha Martin (steel) | Usha Shriram products get Usha International terms | Check invoice seller GSTIN/name before using terms |
| Yamaha | yamaha.com | yes | Yamaha Corporation (music, audio) vs India Yamaha Motor (two-wheelers) — separate companies | Scooter invoices get audio terms | Split by category |
| Hyundai | hyundai.com, hyundai.co.in | yes, both | Hyundai Motor vs "Hyundai" TVs/electronics sold in India under licence | TV invoices get car terms | Resolve by category |
| Wipro | wipro.com | yes | Wipro Ltd (IT services) vs Wipro Consumer Care & Lighting (lighting, appliances) | Verified site has no product warranty | Point to the consumer lighting site after a check |
| Nokia | nokia.com | yes | Nokia Corp (networks) vs HMD Global (makes Nokia phones) | Phone terms come from HMD, not nokia.com | Add HMD site for phones after a check |
| Toshiba | toshiba.com | yes | Toshiba TVs in India are made by Hisense; appliances by Midea | Terms on toshiba.com do not cover these | Review |
| Hitachi | hitachi.com, hitachiaircon.com | aircon only | Hitachi Ltd vs Johnson Controls-Hitachi Air Conditioning (India ACs) | Low (only the aircon site verified) | Keep aircon site only |
| Polar | polarindia.com | no | Polar India (fans) vs Polar (Finnish sports watches) | Watch invoices map to fans | Resolve by category |
| Pigeon | pigeon.in | no | Pigeon (Stovekraft, kitchen) vs Pigeon Corp (Japanese baby products) | Low | Review |
| Prestige | prestige.in | no | TTK Prestige (kitchen) vs Prestige Group (real estate); TTK's site is ttkprestige.com | prestige.in ownership unconfirmed | Check and probably replace with ttkprestige.com |
| Cello | cello.in | yes | Cello World (houseware) vs Cello pens (now BIC) | Low | Keep, review |
| Singer | singerindia.net | yes | Singer India vs Singer global sewing brand (different owners by country) | Low | Keep |
| Sansui | sansui-world.com | no | Brand licensed to different companies by country | Unknown owner of the Indian products | Review |
| Kelvinator | kelvinator.com | no | Electrolux brand abroad; Indian rights differ | Low | Review |
| Kenmore | kenmore.com | yes | US-only brand, not sold in India | Irrelevant entry | Remove? |
| Motorola | motorola.com | yes | Motorola Mobility (Lenovo, phones) vs Motorola Solutions (radios) | Low (motorola.com is the phone maker) | Keep |
| Pioneer | pioneerelectronics.com | yes | Pioneer Corp vs Pioneer DJ (AlphaTheta); site is the US car-audio site | Low | Review |
| Philips | philips.com | yes | Philips vs Philips Domestic Appliances (Versuni, separate since 2021) | Kitchen appliance terms may sit on a Versuni site | Review |
| Orient Fans | orientfan.com | no | Ownership unconfirmed (failed HTTPS in 91.B8); Orient Electric sells fans on orientelectric.com | Low (not verified) | Remove or repoint to orientelectric.com |
| Mahindra | mahindra.com | yes | Group site (cars, tractors, Mahindra Electric) | Low | Keep |

Already handled in code: `brand_registry.AMBIGUOUS` blocks bare matches of common words (hero, orient,
usha, polar, pigeon, prestige, cello, tata, singer, …) unless the invoice context supports them, and
`RETAILERS` (Croma) never become the brand. Section A is about which *website* the terms come from once
the brand is accepted.

## B. Official websites, manually confirmed (`data/oem_manual_confirmed.json`)

These sites return HTTP 403 to the automated checker. Each was opened in a real browser on 2026-10-04 and
the owner was read from the site's own title/footer. Customer label:
"From the official <Brand> website (manually confirmed)".

| Brand | Domains | Evidence (page checked, owner shown on the page) |
|---|---|---|
| LG | lg.com | lg.com/in/support — "LG India"; footer "LG Electronics India Limited" |
| Sony | sony.co.in | sony.co.in/electronics/support — "Sony IN"; footer "Sony India" (sony.com could not be opened from the check browser) |
| Dell | dell.com | dell.com/support/home/en-in — "Dell India"; footer "Dell Inc." |
| Panasonic | panasonic.com | panasonic.com/in/support.html — footer "Panasonic Life Solutions India Pvt. Ltd." |
| Whirlpool | whirlpool.in, whirlpool.com | whirlpoolindia.com redirects to india.whirlpool.in — "Whirlpool India"; whirlpool.com footer "Whirlpool" (US site) |

`sony.co.in` and `whirlpool.in` were added to the registry entries for Sony / Sony India and Whirlpool so
terms from them are accepted as official.
