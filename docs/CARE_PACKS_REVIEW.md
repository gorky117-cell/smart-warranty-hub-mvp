# Care packs review worksheet

Generated from `data/care_packs/*.json` by `python scripts/care_packs_review.py`. Every pack is a **draft**
until approved on /ui/admin/care-packs (customers see only approved packs). Mark each row in the Approve
column (yes / change: ...), then approve the pack on the admin screen.

| Product type | Questions | Tips | Rule problems |
|---|---|---|---|
| Air conditioner (split or window) | 7 | 8 | none |

## Air conditioner (split or window)

Hazards: electric. Matches: air conditioner, split ac, window ac, inverter ac, portable ac, tower ac, cassette ac.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | On a typical summer day, how long does the AC run? | Less than 4 hours / 4 to 8 hours / More than 8 hours | Long daily running wears parts faster and makes filter cleaning more important. | |
| 2 | How often are the filters cleaned? | Every 2 weeks or so / About once a month / Rarely or never | Dirty filters make the AC work harder and cool less. | |
| 3 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power is a common cause of damage to the electronics and the compressor. | |
| 4 | Is the AC connected through a voltage stabilizer? | Yes / No / Not sure | A stabilizer helps when the supply is unsteady (some inverter ACs have their own protection). | |
| 5 | Where is the outdoor unit placed? | Shaded, open space / In direct sun / In a closed or cramped space / It is a window AC | An outdoor unit in direct sun or a closed space cannot release heat well. | |
| 6 | When did the AC last have a service visit? | Within the last 6 months / 6 to 12 months ago / More than a year ago / Never | Regular service catches gas leaks and drain problems early. | |
| 7 | Have you noticed water dripping indoors, weak cooling or unusual noise? | No / Water dripping / Weak cooling / Unusual noise | These are early signs that the AC needs a check. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off the AC at the wall before cleaning the filters. | HIGH | always | Cleaning with the power on risks an electric shock. | |
| 2 | Safety: Don't open the indoor or outdoor unit yourself; leave repairs to the brand's service technicians. | HIGH | always | The units carry high voltage and pressurised refrigerant. | |
| 3 | Clean the filters regularly, more often when the AC runs many hours a day. | HIGH | filter_cleaning = About once a month or Rarely or never; hours_per_day = More than 8 hours | Clean filters keep the air flowing and the cooling strong. | |
| 4 | Use a voltage stabilizer of the right rating if the power at home is unsteady. | HIGH | voltage_issues = Often or Sometimes | Voltage swings can damage the electronics and the compressor. | |
| 5 | Keep space around the outdoor unit clear and, if possible, shade it from direct sun. | MEDIUM | outdoor_unit = In direct sun or In a closed or cramped space | The outdoor unit needs to release heat; blocked or sun-baked units work harder. | |
| 6 | Book a service visit with the brand's authorised service before the summer. | MEDIUM | last_service = More than a year ago or Never | A service catches gas leaks, drain blockages and dirty coils early. | |
| 7 | If water drips indoors, cooling gets weak or you hear new noises, switch the AC off and contact the brand's service. | HIGH | symptoms = Water dripping or Weak cooling or Unusual noise | Running it with a fault can turn a small problem into a bigger one. | |
| 8 | Set a moderate temperature rather than the lowest setting. | LOW | always | Very low settings keep the compressor running for longer. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Clean the AC filters (switch off at the wall first). | about every 2 weeks while in regular use | Check your manual for the interval for your model. | |
| Book an AC service visit. | about every 6 months | Check your manual and warranty card for the recommended service schedule. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| hours_per_day = More than 8 hours | raise | Long daily running wears parts faster. | |
| filter_cleaning = Rarely or never | raise | Dirty filters make the AC work harder. | |
| voltage_issues = Often | raise | Frequent power dips or surges can damage the electronics. | |
| stabilizer = Yes | lower | A stabilizer protects against unsteady power. | |
| outdoor_unit = In direct sun or In a closed or cramped space | raise | An outdoor unit that cannot release heat works harder. | |
| last_service = Within the last 6 months | lower | A recent service catches problems early. | |
| last_service = More than a year ago or Never | raise | Without service, gas leaks and drain blockages go unnoticed. | |
| symptoms = Water dripping or Weak cooling or Unusual noise | raise | These are early signs of a fault. | |

### Usual warranty structure (no numbers)

- **Whole unit:** Covered for a standard period - check your warranty card.
- **Compressor:** Often has its own, separate period - check your warranty card.
- **Gas refill and PCB:** Some brands cover these separately or for a shorter time - check your warranty card.
- **Installation:** Cover may depend on installation by the brand's authorised installer - check your warranty card.

### Exclusions to look for

- Damage from voltage fluctuations or power surges
- Installation or relocation by people the brand has not authorised
- Gas refills or gas leaks
- Damage to the outdoor unit from weather, rust or pests
- Plastic parts, filters and remote controls
- Use in commercial premises
