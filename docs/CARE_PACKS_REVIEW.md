# Care packs review worksheet

Generated from `data/care_packs/*.json` by `python scripts/care_packs_review.py`. Every pack is a **draft**
until approved on /ui/admin/care-packs (customers see only approved packs). Mark each row in the Approve
column (yes / change: ...), then approve the pack on the admin screen.

| Product type | Questions | Tips | Rule problems |
|---|---|---|---|
| Air conditioner (split or window) | 7 | 8 | none |
| Air cooler | 6 | 8 | none |
| Air fryer | 6 | 7 | none |
| Air purifier | 6 | 7 | none |
| Ceiling fan | 6 | 7 | none |
| Earphones or headphones | 6 | 8 | none |
| Gas stove or hob | 6 | 7 | none |
| Induction cooktop | 6 | 7 | none |
| Inverter and battery | 6 | 7 | none |
| Iron or garment steamer | 6 | 8 | none |
| Electric kettle or toaster | 6 | 8 | none |
| Kitchen chimney | 6 | 7 | none |
| Laptop | 7 | 9 | none |
| Microwave or OTG oven | 6 | 8 | none |
| Mixer grinder | 6 | 8 | none |
| Power bank or charger | 6 | 7 | none |
| Printer | 6 | 8 | none |
| Refrigerator | 7 | 9 | none |
| Room heater | 6 | 8 | none |
| Smartphone | 7 | 9 | none |
| Smartwatch or fitness band | 6 | 8 | none |
| Speaker or soundbar | 6 | 8 | none |
| Tablet | 6 | 9 | none |
| Television | 7 | 7 | none |
| Vacuum or robot vacuum | 6 | 8 | none |
| Voltage stabilizer | 6 | 7 | none |
| Washing machine | 7 | 9 | none |
| Water heater / geyser | 6 | 8 | none |
| Water purifier | 6 | 7 | none |
| Wi-Fi router | 6 | 8 | none |

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

## Air cooler

Hazards: electric. Matches: air cooler, desert cooler, personal cooler, tower cooler, cooler.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How often is the water in the tank changed? | Every day or two / About once a week / Rarely | Stale water smells and leaves deposits. | |
| 2 | When were the cooling pads last cleaned or replaced? | This season / Last season / Never | Dirty pads cool less and smell. | |
| 3 | Is the tank emptied and dried before storing it for winter? | Yes / No / It is used all year | Water left in the tank causes smells and damage. | |
| 4 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 5 | Where is the cooler placed? | Near an open window / In a closed room | Coolers work best with fresh air coming in. | |
| 6 | Have you noticed weak air, a smell, leaks or pump noise? | No / Weak cooling / Smell / Leaks / Pump noise | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the cooler before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the cooler yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Change the tank water often and use clean water. | MEDIUM | water_change = About once a week or Rarely | Stale water smells and leaves deposits. | |
| 4 | Clean or replace the cooling pads as the manual suggests. | MEDIUM | pads = Last season or Never | Clean pads cool better. | |
| 5 | Empty and dry the tank before storing the cooler. | MEDIUM | off_season = No | Water left inside causes smells and damage. | |
| 6 | Place the cooler near an open window or door. | LOW | placement = In a closed room | Coolers need fresh air to cool well. | |
| 7 | Don't run the pump when the tank is empty. | MEDIUM | always | Running dry can damage the pump. | |
| 8 | If it leaks or the pump gets noisy, switch it off and contact the brand's service. | MEDIUM | symptoms = Leaks or Pump noise | A failing pump can stop the cooling. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Empty and clean the cooler's water tank. | about once a week in summer | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| water_change = Rarely | raise | Stale water leaves deposits and smells. | |
| pads = Never | raise | Dirty pads make the cooler work harder. | |
| off_season = No | raise | A wet tank in storage causes damage. | |
| symptoms = Leaks or Pump noise | raise | These are early signs of a fault. | |

### Usual warranty structure (no numbers)

- **Cooler:** Covered for a standard period - check your warranty card.
- **Motor and pump:** Some brands cover these separately - check your warranty card.

### Exclusions to look for

- Cooling pads and other consumable parts
- Damage from running the pump dry
- Damage from voltage fluctuations
- Rust and plastic damage

## Air fryer

Hazards: electric. Matches: air fryer, airfryer.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many times a week is it used? | Less than 3 / 3 to 7 / More than 7 | Heavy use wears the heating element and fan. | |
| 2 | Is the basket cleaned after each use? | Yes / Sometimes / No | Old grease can smoke and burn. | |
| 3 | Is there space around the back where the hot air comes out? | Yes / No | Blocked air makes it overheat. | |
| 4 | Where does it stand while in use? | On a heat-safe counter / On another surface | It gets hot underneath and behind. | |
| 5 | Do you use paper or foil liners? | No / Yes | Loose liners can touch the heater. | |
| 6 | Have you noticed smoke, a burning smell or it not heating? | No / Smoke / Burning smell / Not heating | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Unplug the air fryer and let it cool before cleaning it. | HIGH | always | It stays hot and is live while plugged in. | |
| 2 | Safety: Don't open the air fryer yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Safety: Don't bypass or tamper with the thermostat or any safety cut-out. | HIGH | always | These stop the appliance overheating; without them it can cause burns or a fire. | |
| 4 | Clean the basket and tray after each use. | MEDIUM | basket_cleaning = Sometimes or No | Old grease can smoke and burn. | |
| 5 | Keep space around the back and sides. | MEDIUM | placement = No | Blocked air makes it overheat. | |
| 6 | Use only liners your manual allows, and never let them cover the heater. | MEDIUM | liners = Yes | Loose liners can catch fire. | |
| 7 | If it smokes or smells of burning, unplug it and contact the brand's service. | HIGH | symptoms = Smoke or Burning smell or Not heating | These can be signs of a fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Deep-clean the air fryer's basket and tray (unplugged and cool). | about every 2 weeks with regular use | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| basket_cleaning = No | raise | Old grease can smoke and burn. | |
| placement = No | raise | Blocked air makes it overheat. | |
| liners = Yes | raise | Loose liners can touch the heater. | |
| symptoms = Smoke or Burning smell or Not heating | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Air fryer:** Covered for a standard period - check your warranty card.
- **Basket and coating:** Often not covered for wear or scratches - check your warranty card.

### Exclusions to look for

- Scratches or wear on the non-stick coating
- Damage from unsuitable liners or utensils
- Damage from voltage fluctuations
- Burn marks

## Air purifier

Hazards: electric. Matches: air purifier, hepa purifier.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many hours a day does it run? | Less than 8 hours / 8 to 16 hours / More than 16 hours | Long running fills the filter faster. | |
| 2 | How is the air outside your home usually? | Usually good / Moderate / Often poor | Polluted air fills the filter faster. | |
| 3 | When was the filter last changed? | Within 6 months / More than 6 months ago / Never | A full filter stops cleaning the air. | |
| 4 | How often is the pre-filter cleaned? | About once a month / Rarely / It has no pre-filter | A dusty pre-filter blocks the air. | |
| 5 | Is there space around the air inlets and outlet? | Yes / No | Blocked air cuts its performance. | |
| 6 | Have you noticed a smell, loud fan or a filter warning? | No / Smell / Loud fan / Filter warning | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the air purifier before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the air purifier yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Change the main filter when the indicator or your manual says so. | HIGH | filter_change = More than 6 months ago or Never; symptoms = Filter warning | A full filter stops cleaning the air. | |
| 4 | Clean the pre-filter as the manual describes. | MEDIUM | pre_filter = Rarely | A dusty pre-filter blocks the air. | |
| 5 | Keep space around the inlets and outlet. | LOW | placement = No | Blocked air cuts its performance. | |
| 6 | Use filters made for your model. | MEDIUM | always | Ill-fitting filters let dust bypass them. | |
| 7 | If the fan gets loud or there is a smell after a filter change, contact the brand's service. | MEDIUM | symptoms = Smell or Loud fan | These can be signs of a fan problem. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Clean the air purifier's pre-filter (unplugged). | about once a month | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| hours_per_day = More than 16 hours | raise | Long running fills the filter faster. | |
| air_quality = Often poor | raise | Polluted air fills the filter faster. | |
| filter_change = Never | raise | A full filter strains the fan. | |
| symptoms = Smell or Loud fan | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Air purifier:** Covered for a standard period - check your warranty card.
- **Filters:** Usually consumables, not covered - check your warranty card.

### Exclusions to look for

- Filters and other consumables
- Damage from filters not made for the model
- Damage from voltage fluctuations

## Ceiling fan

Hazards: electric. Matches: ceiling fan, bldc fan, fan.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many hours a day does the fan run? | Less than 8 hours / 8 to 16 hours / More than 16 hours | Long running wears the motor and bearings. | |
| 2 | Does the fan wobble or make a clicking sound? | No / A little / A lot | Wobble can mean loose fittings or unbalanced blades. | |
| 3 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 4 | Is the speed regulator working smoothly? | Yes / No / Not sure | A faulty regulator can strain the motor. | |
| 5 | Who installed the fan? | An electrician or the brand's technician / Someone else / Not sure | Fittings and wiring need to be done properly for safety. | |
| 6 | How often are the blades cleaned? | About once a month / Rarely | Dust adds weight and unbalances the blades. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off the fan at the wall and wait for the blades to stop before cleaning them. | HIGH | always | Cleaning a moving or powered fan risks injury and electric shock. | |
| 2 | Safety: Don't open the fan motor yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | If the fan wobbles or clicks, stop using it and have the fittings checked by an electrician or the brand's service. | HIGH | wobble = A little or A lot | Loose fittings can make a fan fall. | |
| 4 | Have the mounting and wiring checked by a qualified electrician. | HIGH | installed_by = Someone else or Not sure | Proper fittings keep the fan secure. | |
| 5 | Wipe the blades gently with a dry cloth. | LOW | dust = Rarely | Dust unbalances the blades. | |
| 6 | Have a faulty regulator replaced by an electrician. | MEDIUM | regulator = No | A faulty regulator strains the motor. | |
| 7 | If the power is unsteady, ask an electrician about protection for the circuit. | MEDIUM | power_issues = Often | Power swings can damage the motor. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Wipe the fan blades (switched off at the wall). | about once a month | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| hours_per_day = More than 16 hours | raise | Long running wears the motor. | |
| wobble = A lot | raise | Wobble can mean loose fittings. | |
| installed_by = An electrician or the brand's technician | lower | Proper installation keeps the fan secure. | |
| power_issues = Often | raise | Power swings can damage the motor. | |

### Usual warranty structure (no numbers)

- **Fan:** Covered for a standard period - check your warranty card.
- **Motor:** Some brands cover the motor for longer - check your warranty card.

### Exclusions to look for

- Damage from voltage fluctuations
- Installation by people the brand has not authorised
- Rust and paint damage
- Damage to blades from bending or impact

## Earphones or headphones

Hazards: electric, battery. Matches: earphones, headphones, earbuds, tws, neckband, headset, true wireless.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How is the case or headphone charged? | With a branded charger / With a cheap charger / They are wired, no battery | Poor chargers can damage the small batteries. | |
| 2 | Are they used during workouts or in the rain? | Rarely / Often | Sweat and water can get into the speakers and charging contacts. | |
| 3 | How loud are they usually played? | Moderate / Loud | Very loud sound strains the speakers and your hearing. | |
| 4 | Are they kept in their case when not in use? | Yes / No | The case protects against drops and dirt. | |
| 5 | How often are the ear tips and mesh cleaned? | About once a week / Rarely | Earwax and dirt block the sound. | |
| 6 | Have you noticed one side not working, charging problems or crackling? | No / One side not working / Charging problems / Crackling | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Stop using the earphones or case and keep it away from anything that can burn if the battery swells, gets very hot or smells unusual. | HIGH | always | A damaged battery can catch fire. | |
| 2 | Safety: Don't open, puncture or crush the battery, and don't use it after a hard fall that dented it. | HIGH | always | Damaged battery cells can overheat or catch fire. | |
| 3 | Safety: Switch the earphones or case off and unplug the charger before cleaning it. | HIGH | always | Cleaning a charging device risks a short circuit. | |
| 4 | Charge with a branded charger and cable. | MEDIUM | charger = With a cheap charger | Cheap chargers can damage the small batteries. | |
| 5 | Wipe off sweat and water, and let them dry before charging. | MEDIUM | sweat = Often | Moisture damages the speakers and contacts. | |
| 6 | Keep the volume moderate. | LOW | volume = Loud | Very loud sound strains the speakers and your hearing. | |
| 7 | Keep them in their case when not in use. | LOW | storage = No | The case protects against drops and dirt. | |
| 8 | Clean the ear tips and mesh gently with a dry cloth. | LOW | cleaning = Rarely | Wax and dirt block the sound. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Clean the ear tips, mesh and charging contacts. | about once a week | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| charger = With a cheap charger | raise | Cheap chargers can damage the battery. | |
| sweat = Often | raise | Moisture can damage the speakers. | |
| storage = Yes | lower | The case protects against drops. | |
| symptoms = One side not working or Charging problems or Crackling | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Earphones or headphones:** Covered for a standard period - check your warranty card.
- **Case, ear tips and cables:** Often not covered or covered for a shorter time - check your warranty card.

### Exclusions to look for

- Physical damage and lost parts
- Water or sweat damage beyond the stated rating
- Ear tips and cables
- Battery wear

## Gas stove or hob

Hazards: gas. Matches: gas stove, gas hob, hob, cooktop, burner.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | When was the gas hose last checked or changed? | Within the last year / More than a year ago / Not sure | Old or cracked hoses can leak. | |
| 2 | What colour is the flame? | Steady blue / Yellow or uneven | A yellow or uneven flame can mean blocked burners. | |
| 3 | Does the automatic ignition (if any) work first time? | Yes / No / No automatic ignition | Repeated clicking can mean a fault. | |
| 4 | Is the kitchen well ventilated while cooking? | Yes / No | Fresh air keeps gas from collecting. | |
| 5 | How often are the burners cleaned? | About once a week / Rarely | Spills block the burner holes. | |
| 6 | Have you ever smelled gas near the stove? | No / Yes | A gas smell needs urgent attention. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: If you smell gas: close the gas supply, don't switch anything electrical on or off, open doors and windows to ventilate, and call your gas or service number from outside. | HIGH | always | A spark in a room full of gas can cause an explosion. | |
| 2 | Safety: Turn the knobs and the gas supply off when you finish cooking. | HIGH | always | This stops gas escaping. | |
| 3 | Safety: Have the gas hose checked, and replaced when it is old or cracked, by your gas provider or the brand's service. | HIGH | hose_age = More than a year ago or Not sure | Old hoses can leak. | |
| 4 | Keep a window open or the chimney on while cooking. | MEDIUM | ventilation = No | Fresh air stops gas collecting. | |
| 5 | Clean the burners as the manual describes once they are cool. | MEDIUM | cleaning = Rarely; flame = Yellow or uneven | Clean burners give a steady blue flame. | |
| 6 | If the flame stays yellow or uneven, contact the brand's service. | MEDIUM | flame = Yellow or uneven | It can mean the gas is not burning properly. | |
| 7 | If the ignition keeps clicking without lighting, turn the knob off and contact the brand's service. | LOW | ignition = No | Unlit gas can collect. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Check the gas hose for cracks and ask for it to be checked. | about every 6 months | Check your manual and your gas provider's advice. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| hose_age = More than a year ago or Not sure | raise | Old hoses can leak. | |
| flame = Yellow or uneven | raise | A yellow flame can mean blocked burners. | |
| ventilation = No | raise | Poor ventilation lets gas collect. | |
| smell = Yes | raise | A gas smell needs urgent attention. | |
| cleaning = About once a week | lower | Clean burners burn better. | |

### Usual warranty structure (no numbers)

- **Stove body:** Covered for a standard period - check your warranty card.
- **Glass top:** Often not covered for breakage - check your warranty card.
- **Burners and knobs:** Some parts may be covered separately - check your warranty card.

### Exclusions to look for

- Broken or cracked glass
- Gas hoses and regulators
- Rust and discolouration
- Installation by people the brand has not authorised

## Induction cooktop

Hazards: electric. Matches: induction, induction cooktop, induction stove, induction cooker.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How long is it used each day? | Less than an hour / 1 to 3 hours / More than 3 hours | Long cooking heats the electronics inside. | |
| 2 | What cookware is used on it? | Induction-ready pans / A mix / Not sure | Only induction-ready cookware works well; the wrong kind can damage it. | |
| 3 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 4 | Are the air vents kept clear? | Yes / No | Blocked vents make it overheat. | |
| 5 | Do spills often reach the vents or the control panel? | No / Sometimes | Liquid can damage the electronics. | |
| 6 | Have you noticed error codes, cracks on the glass or it switching off by itself? | No / Error codes / Cracked glass / Switches off | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the cooktop, and let the glass cool, before cleaning it. | HIGH | always | The surface stays hot and cleaning it while powered risks a shock. | |
| 2 | Safety: Don't open the cooktop yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Safety: Stop using it if the glass is cracked, and contact the brand's service. | HIGH | symptoms = Cracked glass | Cracked glass can let liquid reach live parts. | |
| 4 | Use induction-ready cookware with a flat base. | MEDIUM | cookware = A mix or Not sure | The wrong cookware heats poorly and can trigger errors. | |
| 5 | Keep the air vents clear. | MEDIUM | vents = No | Blocked vents make it overheat. | |
| 6 | Use a surge protector or stabilizer if the power is unsteady. | MEDIUM | power_issues = Often or Sometimes | Power swings can damage the board. | |
| 7 | Wipe spills once the glass has cooled. | LOW | spills = Sometimes | Burnt spills are harder to clean and can stain. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Check the cooktop's air vents are clean (unplugged and cool). | about once a month | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| power_issues = Often | raise | Power swings can damage the board. | |
| cookware = A mix | raise | The wrong cookware strains the coil. | |
| vents = No | raise | Blocked vents cause overheating. | |
| symptoms = Error codes or Cracked glass or Switches off | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Cooktop:** Covered for a standard period - check your warranty card.
- **Glass top:** Often not covered for breakage - check your warranty card.

### Exclusions to look for

- Cracked or broken glass
- Damage from voltage fluctuations
- Damage from liquid spills into the vents
- Burn marks

## Inverter and battery

Hazards: electric, battery. Matches: inverter battery, home ups, ups, tubular battery, inverter.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How often does the power go out? | Rarely / A few times a week / Every day | Frequent cuts mean more charge and discharge cycles. | |
| 2 | What runs on the inverter during a cut? | Lights and fans / Heavy appliances too / Not sure | Running more than it is rated for overheats it. | |
| 3 | Where are the inverter and battery kept? | In an open, airy place / In a closed cabinet or small space | They give off heat and gas and need fresh air. | |
| 4 | If the battery has a water level indicator, when was it last checked by a technician? | Within the last 3 months / Longer ago / It is a sealed battery | Low water shortens the battery's life. | |
| 5 | Has the backup time become shorter? | No / A little / A lot | Shorter backup is a sign the battery is wearing. | |
| 6 | Have you noticed beeping, a smell, a swollen battery or corrosion on the terminals? | No / Beeping or alarms / A smell / Swelling / White or green deposits | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: If the battery swells, leaks or smells, switch the inverter off and call the brand's service; don't touch the terminals. | HIGH | always | A damaged battery can leak acid or catch fire. | |
| 2 | Safety: Switch off the inverter at the mains before cleaning around it. | HIGH | always | It stays live while connected. | |
| 3 | Safety: Don't open the inverter or the battery; leave checks and top-ups to the brand's technician. | HIGH | always | Battery acid and live parts are dangerous. | |
| 4 | Keep the inverter and battery in an open, airy place away from children. | HIGH | ventilation = In a closed cabinet or small space | They give off heat and gas. | |
| 5 | Run only what the inverter is rated for during cuts. | MEDIUM | load = Heavy appliances too or Not sure | Overloading overheats it. | |
| 6 | Ask the technician to check the battery's water level at service visits. | MEDIUM | water_level = Longer ago | Low water shortens the battery's life. | |
| 7 | If backup time drops a lot or it keeps beeping, contact the brand's service. | MEDIUM | backup_time = A lot; symptoms = Beeping or alarms or White or green deposits | The battery may need a check. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Book an inverter and battery check. | about every 3 months | Check your manual and warranty card for the recommended service schedule. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| cuts_per_week = Every day | raise | Daily cuts mean more battery cycles. | |
| load = Heavy appliances too | raise | Overloading overheats the inverter. | |
| ventilation = In a closed cabinet or small space | raise | Heat shortens battery life. | |
| water_level = Within the last 3 months or It is a sealed battery | lower | A maintained battery lasts longer. | |
| symptoms = A smell or Swelling or White or green deposits or Beeping or alarms | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Inverter:** Covered for a standard period - check your warranty card.
- **Battery:** Often split into a full-replacement period and a pro-rata period - check your warranty card.

### Exclusions to look for

- Battery damage from low water or overloading
- Physical damage or a broken case
- Damage from wrong installation
- Pro-rata terms in later years

## Iron or garment steamer

Hazards: electric. Matches: iron, dry iron, steam iron, garment steamer, steamer.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many times a week is it used? | Less than 3 / 3 to 7 / More than 7 | Heavy use wears the soleplate and heater. | |
| 2 | What water goes in the steam tank? | Filtered or the type the manual says / Tap water / It is a dry iron | Hard water leaves scale that blocks the steam holes. | |
| 3 | Is it ever left on and unattended? | No / Sometimes | An unattended hot iron is a fire risk. | |
| 4 | Is the power cord in good condition? | Yes / Worn or damaged | Damaged cords are a shock and fire risk. | |
| 5 | How is it stored after use? | Cooled and empty / Still hot or with water | Storing it hot or with water inside causes damage. | |
| 6 | Have you noticed leaks, spitting water, a burning smell or sparks? | No / Leaks or spitting / Burning smell / Sparks | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the iron before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the iron yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Safety: Don't bypass or tamper with the thermostat or any safety cut-out. | HIGH | always | These stop the appliance overheating; without them it can cause burns or a fire. | |
| 4 | Safety: Unplug the iron whenever you step away. | HIGH | left_on = Sometimes | An unattended hot iron can start a fire. | |
| 5 | Safety: Stop using it if the cord is worn or damaged, and contact the brand's service. | HIGH | cord = Worn or damaged | Damaged cords can cause shocks and fires. | |
| 6 | Use the type of water your manual recommends. | MEDIUM | water = Tap water | Hard water leaves scale that blocks the steam holes. | |
| 7 | Let it cool and empty the tank before putting it away. | LOW | storage = Still hot or with water | Water and heat left inside cause damage. | |
| 8 | If it sparks or smells of burning, unplug it and contact the brand's service. | HIGH | symptoms = Burning smell or Sparks | These can be signs of a dangerous fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Run the iron's self-clean or descale as your manual describes. | about once a month for steam irons | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| water = Tap water | raise | Hard water leaves scale. | |
| left_on = Sometimes | raise | An unattended iron is a fire risk. | |
| cord = Worn or damaged | raise | A damaged cord is a shock and fire risk. | |
| symptoms = Leaks or spitting or Burning smell or Sparks | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Iron or steamer:** Covered for a standard period - check your warranty card.
- **Soleplate coating:** Often not covered for scratches or wear - check your warranty card.

### Exclusions to look for

- Scratches or damage to the soleplate
- Damage from scale or the wrong water
- Damage from voltage fluctuations
- Burn marks

## Electric kettle or toaster

Hazards: electric. Matches: kettle, electric kettle, toaster, pop-up toaster, sandwich maker.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | Which appliance is it? | Kettle / Toaster or sandwich maker | Kettles and toasters need different care. | |
| 2 | Does your water leave white marks in the kettle? | No / Some / A lot / It is a toaster | Scale builds up on the heating plate. | |
| 3 | Is the kettle filled above the maximum line? | No / Sometimes / It is a toaster | Overfilling can spill boiling water. | |
| 4 | How often is the crumb tray emptied? | About once a week / Rarely / It is a kettle | Built-up crumbs can burn. | |
| 5 | Is the power cord in good condition? | Yes / Worn or damaged | Damaged cords are a shock and fire risk. | |
| 6 | Have you noticed it not switching off, a burning smell or sparks? | No / Does not switch off / Burning smell / Sparks | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the appliance before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the appliance yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Safety: Don't bypass or tamper with the thermostat or any safety cut-out. | HIGH | always | These stop the appliance overheating; without them it can cause burns or a fire. | |
| 4 | Safety: Stop using it if the cord is worn or damaged, and contact the brand's service. | HIGH | cord = Worn or damaged | Damaged cords can cause shocks and fires. | |
| 5 | Descale the kettle as the manual describes. | MEDIUM | water_hard = Some or A lot | Scale makes the heating plate work harder. | |
| 6 | Fill the kettle between the minimum and maximum lines. | MEDIUM | overfill = Sometimes | Overfilling spills boiling water. | |
| 7 | Empty the toaster's crumb tray regularly (unplugged and cool). | MEDIUM | crumbs = Rarely | Crumbs can burn. | |
| 8 | If it does not switch off by itself or smells of burning, unplug it and contact the brand's service. | HIGH | symptoms = Does not switch off or Burning smell or Sparks | The automatic cut-off may have failed. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Descale the kettle or empty the toaster's crumb tray (unplugged). | about once a month | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| water_hard = A lot | raise | Scale makes the heating plate work harder. | |
| crumbs = Rarely | raise | Built-up crumbs can burn. | |
| cord = Worn or damaged | raise | A damaged cord is a shock and fire risk. | |
| symptoms = Does not switch off or Burning smell or Sparks | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Appliance:** Covered for a standard period - check your warranty card.
- **Glass and plastic parts:** Often not covered for breakage - check your warranty card.

### Exclusions to look for

- Damage from scale or hard water
- Broken glass or plastic
- Damage from voltage fluctuations
- Burn marks

## Kitchen chimney

Hazards: electric. Matches: chimney, kitchen hood, cooker hood, range hood.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How much frying or oily cooking is done? | Little / Some / A lot | Oil clogs the filters faster. | |
| 2 | How often are the filters cleaned (or the auto-clean run)? | About once a month / Rarely / Never | Clogged filters reduce suction and strain the motor. | |
| 3 | How is the chimney vented? | Short straight duct / Long or bent duct / Not sure | Long or bent ducts reduce suction. | |
| 4 | Was it installed by the brand's technician at the recommended height? | Yes / Not sure / No | Height and fitting affect suction and safety. | |
| 5 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 6 | Have you noticed weak suction, oil dripping or loud noise? | No / Weak suction / Oil dripping / Loud noise | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off the chimney at the wall before cleaning the filters. | HIGH | always | Cleaning while powered risks a shock. | |
| 2 | Safety: Don't open the chimney motor yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Clean the filters (or run the auto-clean) as your manual describes. | HIGH | filter_cleaning = Rarely or Never; cooking = A lot | Clogged filters reduce suction and strain the motor. | |
| 4 | Keep the chimney running for a few minutes after cooking. | LOW | always | This clears the remaining smoke and moisture. | |
| 5 | Ask the brand's service to check the height and duct if suction is weak. | MEDIUM | height = No or Not sure; duct = Long or bent duct | Poor fitting reduces suction. | |
| 6 | Use a surge protector if the power is unsteady. | MEDIUM | power_issues = Often | Power swings can damage the motor and controls. | |
| 7 | If suction gets weak, oil drips or the noise gets loud, contact the brand's service. | MEDIUM | symptoms = Weak suction or Oil dripping or Loud noise | A clogged or failing motor gets worse with use. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Clean the chimney filters or run the auto-clean. | about once a month with regular cooking | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| cooking = A lot | raise | Oil clogs the filters faster. | |
| filter_cleaning = Never | raise | Clogged filters strain the motor. | |
| duct = Long or bent duct | raise | Long or bent ducts reduce suction. | |
| symptoms = Weak suction or Oil dripping or Loud noise | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Chimney:** Covered for a standard period - check your warranty card.
- **Motor:** Some brands cover the motor for longer - check your warranty card.

### Exclusions to look for

- Filters and other consumable parts
- Damage from oil build-up when filters are not cleaned
- Ducting and installation materials
- Installation by people the brand has not authorised

## Laptop

Hazards: electric, battery. Matches: laptop, notebook, ultrabook, chromebook, macbook.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many hours a day is the laptop used? | Less than 4 hours / 4 to 8 hours / More than 8 hours | Long daily use wears the battery, fans and keyboard. | |
| 2 | Where is it usually used? | On a desk or table / On a bed or sofa / On the lap | Soft surfaces block the air vents and trap heat. | |
| 3 | Which charger is usually used? | The one it came with / Another branded charger / A cheap or unbranded one / Whatever is around | Poor or mismatched chargers are a common cause of battery and port damage. | |
| 4 | Are your files backed up? | Yes / Sometimes / No | A backup protects your work if a repair or drive fails. | |
| 5 | How is it carried around? | In a padded bag / In an ordinary bag / Rarely moved | Padding protects against knocks. | |
| 6 | Do you eat or drink near the laptop? | No / Sometimes / Often | Spills are a common cause of keyboard and board damage. | |
| 7 | Have you noticed loud fans, overheating, a swollen battery or a slow start? | No / Overheating or loud fans / Swollen battery or lifting touchpad / Very slow | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Stop using the laptop and keep it away from anything that can burn if the battery swells, gets very hot or smells unusual. | HIGH | always | A damaged battery can catch fire. | |
| 2 | Safety: Don't open, puncture or crush the battery, and don't use it after a hard fall that dented it. | HIGH | always | Damaged battery cells can overheat or catch fire. | |
| 3 | Safety: Switch off and unplug the laptop before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 4 | Use the laptop on a hard, flat surface so the vents are not blocked. | MEDIUM | surface = On a bed or sofa or On the lap | Blocked vents make it overheat. | |
| 5 | Use the laptop's own charger or one with the same rating from the brand. | HIGH | charger = A cheap or unbranded one or Whatever is around | A wrong charger can damage the battery and the charging circuit. | |
| 6 | Back up your files regularly. | HIGH | backup = Sometimes or No | A repair or a failed drive can lose your data. | |
| 7 | Keep drinks away from the keyboard. | MEDIUM | food_drink = Sometimes or Often | Spills damage the keyboard and the board inside. | |
| 8 | Carry the laptop in a padded bag. | LOW | carry = In an ordinary bag | Padding protects against knocks. | |
| 9 | If it overheats, the fans get loud or it slows down a lot, contact the brand's service. | MEDIUM | symptoms = Overheating or loud fans or Very slow | These can be signs of a cooling or drive problem. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Back up the files on your laptop. | about once a month | Check your manual or system settings for automatic backup. | |
| Check the laptop's vents are free of dust (switched off and unplugged). | about every 3 months | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| hours_per_day = More than 8 hours | raise | Long daily use wears the battery and fans. | |
| surface = On a bed or sofa or On the lap | raise | Blocked vents make it run hot. | |
| charger = A cheap or unbranded one or Whatever is around | raise | A wrong charger can damage the battery. | |
| food_drink = Often | raise | Spills are a common cause of damage. | |
| carry = In a padded bag | lower | A padded bag protects against knocks. | |
| symptoms = Overheating or loud fans or Swollen battery or lifting touchpad or Very slow | raise | These are early signs of a fault. | |

### Usual warranty structure (no numbers)

- **Laptop:** Covered for a standard period - check your warranty card.
- **Battery:** Often covered for a shorter period - check your warranty card.
- **Charger and accessories:** Often covered separately - check your warranty card.

### Exclusions to look for

- Liquid damage and spills
- Physical damage, including a cracked screen
- Software problems, viruses and data loss
- Repairs by people the brand has not authorised
- Damage from chargers that are not genuine

## Microwave or OTG oven

Hazards: electric. Matches: microwave, otg, oven toaster grill, convection, oven.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many times a day is it used? | Less than 3 / 3 to 6 / More than 6 | Heavy use wears the heating parts and door switches. | |
| 2 | Which containers go in a microwave? | Only microwave-safe ones / Whatever is at hand / It is an OTG | Metal and some plastics can spark or melt. | |
| 3 | How often is the inside cleaned? | About once a week / Rarely | Food splashes absorb energy and can burn. | |
| 4 | Does the door close firmly and the seal look clean? | Yes / Not sure / No | A good door seal keeps the heat and microwaves inside. | |
| 5 | Is there space around the vents? | Yes / It is boxed in | Blocked vents make it overheat. | |
| 6 | Have you noticed sparks, a burning smell, or it not heating? | No / Sparks / Burning smell / Not heating | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the oven before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the oven yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Safety: Never run a microwave empty. | HIGH | always | Running it empty can damage it. | |
| 4 | Use only microwave-safe containers and no metal in a microwave. | HIGH | containers = Whatever is at hand | Metal sparks and some plastics melt. | |
| 5 | Wipe the inside and the door seal regularly. | MEDIUM | cleaning = Rarely | Food splashes can burn and damage the cavity. | |
| 6 | If the door does not close firmly, stop using it and contact the brand's service. | HIGH | door = No or Not sure | A poor door seal is unsafe. | |
| 7 | Leave space around the vents. | MEDIUM | ventilation = It is boxed in | Blocked vents make it overheat. | |
| 8 | If it sparks, smells of burning or stops heating, unplug it and contact the brand's service. | HIGH | symptoms = Sparks or Burning smell or Not heating | These can be signs of a dangerous fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Wipe the inside and door seal of the oven (unplugged). | about once a week | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| uses_per_day = More than 6 | raise | Heavy use wears the heating parts. | |
| containers = Whatever is at hand | raise | Metal or unsafe containers can damage it. | |
| cleaning = Rarely | raise | Built-up food can burn inside. | |
| door = No | raise | A poor door seal is unsafe. | |
| symptoms = Sparks or Burning smell or Not heating | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Oven:** Covered for a standard period - check your warranty card.
- **Magnetron or heating element:** Some brands cover these for longer - check your warranty card.

### Exclusions to look for

- Damage from metal or unsuitable containers
- Glass trays, bulbs and other accessories
- Rust inside the cavity
- Damage from voltage fluctuations

## Mixer grinder

Hazards: electric. Matches: mixer grinder, mixer, grinder, juicer mixer, food processor, blender, hand blender.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many times a day is it used? | Less than 2 / 2 to 4 / More than 4 | Heavy use heats the motor. | |
| 2 | Is it run for long stretches without a break? | No / Sometimes / Yes | Long runs overheat the motor. | |
| 3 | Are the jars filled above the marked line? | No / Sometimes / Yes | Overfilling strains the motor and can leak. | |
| 4 | Do you grind hard items like dry spices, ice or grains often? | Rarely / Often | Hard items load the blades and motor. | |
| 5 | Do the jar lids and gaskets seal well? | Yes / No | Worn gaskets let liquid reach the motor. | |
| 6 | Have you noticed a burning smell, the motor stopping or loud noise? | No / Burning smell / Stops by itself / Loud noise | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the mixer before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the mixer motor yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Safety: Handle the blades carefully and keep them away from children. | HIGH | always | The blades are very sharp. | |
| 4 | Run it in short bursts and let the motor rest between runs. | HIGH | long_runs = Sometimes or Yes | Long runs overheat the motor. | |
| 5 | Don't fill the jars above the marked line. | MEDIUM | overfill = Sometimes or Yes | Overfilling strains the motor and can spill. | |
| 6 | Use the right jar for hard items and grind in small amounts. | MEDIUM | hard_items = Often | Hard items load the blades and motor. | |
| 7 | Replace worn jar gaskets with genuine ones. | LOW | jar_seal = No | Worn gaskets let liquid reach the motor. | |
| 8 | If you smell burning or the motor keeps stopping, unplug it and contact the brand's service. | HIGH | symptoms = Burning smell or Stops by itself or Loud noise | These can be signs of an overheating motor. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Check the jar gaskets and couplers for wear (unplugged). | about every 3 months | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| long_runs = Yes | raise | Long runs overheat the motor. | |
| overfill = Yes | raise | Overfilling strains the motor. | |
| hard_items = Often | raise | Hard items load the motor. | |
| uses_per_day = More than 4 | raise | Heavy use heats the motor. | |
| symptoms = Burning smell or Stops by itself or Loud noise | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Mixer:** Covered for a standard period - check your warranty card.
- **Motor:** Often has its own, longer period - check your warranty card.
- **Jars, blades and gaskets:** Often covered for a shorter time or not at all - check your warranty card.

### Exclusions to look for

- Jars, blades, gaskets and couplers
- Motor damage from overloading
- Damage from voltage fluctuations
- Broken plastic parts

## Power bank or charger

Hazards: electric, battery. Matches: power bank, powerbank, charger, adapter, fast charger, charging cable.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | Which is it? | Power bank / Wall charger or cable | Power banks and wall chargers need different care. | |
| 2 | Is it used or left in hot places, such as a car or in the sun? | No / Yes | Heat damages batteries and electronics. | |
| 3 | What cable is used with it? | The one it came with or a branded one / A cheap or damaged one | Damaged or poor cables can overheat. | |
| 4 | Has it been dropped hard? | No / Yes | A hard drop can damage the battery inside a power bank. | |
| 5 | Is it charged under pillows or on beds? | No / Yes | Soft surfaces trap heat. | |
| 6 | Have you noticed swelling, very high heat, a smell or sparks? | No / Swelling / Very hot / A smell / Sparks | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Stop using the power bank and keep it away from anything that can burn if the battery swells, gets very hot or smells unusual. | HIGH | always | A damaged battery can catch fire. | |
| 2 | Safety: Don't open, puncture or crush the battery, and don't use it after a hard fall that dented it. | HIGH | always | Damaged battery cells can overheat or catch fire. | |
| 3 | Safety: Unplug the charger from the wall before cleaning it, and don't use it if it is damaged or wet. | HIGH | always | A damaged or wet charger can give a shock. | |
| 4 | Use a branded cable in good condition. | MEDIUM | cable = A cheap or damaged one | Damaged cables can overheat. | |
| 5 | Charge on a hard, cool surface, not under pillows or on beds. | MEDIUM | overnight = Yes | Soft surfaces trap heat. | |
| 6 | Keep it out of hot cars and direct sun. | MEDIUM | heat = Yes | Heat damages batteries. | |
| 7 | After a hard drop, watch the power bank for heat or swelling and stop using it if either appears. | MEDIUM | drops = Yes | Inner damage can show up later. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Check the power bank and cables for damage, swelling or heat. | about every 3 months | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| heat = Yes | raise | Heat damages batteries. | |
| cable = A cheap or damaged one | raise | Poor cables can overheat. | |
| drops = Yes | raise | A drop can damage the battery. | |
| symptoms = Swelling or Very hot or A smell or Sparks | raise | These are signs of a dangerous fault. | |

### Usual warranty structure (no numbers)

- **Power bank or charger:** Covered for a standard period - check your warranty card.
- **Cable:** Often covered for a shorter time - check your warranty card.

### Exclusions to look for

- Physical damage or a swollen case
- Damage from heat or water
- Cables
- Battery wear

## Printer

Hazards: electric. Matches: printer, ink tank, inkjet, laserjet, laser printer, all-in-one.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many pages are printed in a month? | Fewer than 50 / 50 to 300 / More than 300 | Heavy printing wears parts faster; very little printing can let ink dry. | |
| 2 | Does the printer sometimes sit unused for weeks? | No / Yes | Ink can dry in the print head when it is not used. | |
| 3 | Which ink or toner do you use? | The brand's own / Other or refilled / Not sure | The wrong ink or toner can block the print head. | |
| 4 | Which paper do you use? | Normal office paper / Whatever is around | Damp, thick or crumpled paper causes jams. | |
| 5 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 6 | Have you noticed paper jams, faded or streaky prints or error lights? | No / Paper jams / Faded or streaky prints / Error lights | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the printer before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the printer yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Print a page every week or two if the printer sits idle. | MEDIUM | idle = Yes | Ink can dry in the print head. | |
| 4 | Use the ink or toner the brand recommends for your model. | HIGH | ink = Other or refilled or Not sure | The wrong ink can block the print head. | |
| 5 | Use dry, flat paper of the type your manual lists. | LOW | paper = Whatever is around | Damp or crumpled paper jams the rollers. | |
| 6 | Keep the printer covered from dust when not in use. | LOW | always | Dust affects the rollers and prints. | |
| 7 | Plug it into a surge protector if the power is unsteady. | MEDIUM | power_issues = Often or Sometimes | Power spikes can damage the board. | |
| 8 | For repeated jams, streaky prints or error lights, follow the manual's checks, then contact the brand's service. | MEDIUM | symptoms = Paper jams or Faded or streaky prints or Error lights | Forcing jammed paper can damage the rollers. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Print a test page so the ink does not dry. | about every 2 weeks if the printer is idle | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| pages_per_month = More than 300 | raise | Heavy printing wears parts faster. | |
| idle = Yes | raise | Ink can dry in the print head. | |
| ink = Other or refilled | raise | The wrong ink can block the print head. | |
| ink = The brand's own | lower | Recommended ink suits the print head. | |
| symptoms = Paper jams or Faded or streaky prints or Error lights | raise | These are early signs of a fault. | |

### Usual warranty structure (no numbers)

- **Printer:** Covered for a standard period, sometimes limited by the number of pages printed - check your warranty card.
- **Print head:** Some brands cover it separately or with conditions - check your warranty card.
- **Ink, toner and cartridges:** Consumables are usually not covered - check your warranty card.

### Exclusions to look for

- Damage from ink or toner that is not genuine
- Ink, toner and other consumables
- Damage from paper jams caused by the wrong paper
- Damage from power surges
- Repairs by people the brand has not authorised

## Refrigerator

Hazards: electric. Matches: refrigerator, fridge, double door, single door, side by side, freezer.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | Does the door close firmly with the seal touching all round? | Yes / Not always / No | A leaking seal lets cold air out and makes the compressor work harder. | |
| 2 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 3 | Is it plugged into a surge protector or stabilizer? | Yes / No / Not sure | These protect against power spikes. | |
| 4 | How much space is there behind and beside the fridge? | A hand's width or more / Very little / Not sure | The fridge releases heat at the back and sides. | |
| 5 | How full is the fridge usually? | Normal / Packed tight / Mostly empty | Packing it too tight blocks the cold air from moving. | |
| 6 | Is there thick ice inside the freezer? | No / A little / Thick ice | Thick ice means the fridge works harder (or a defrost problem on frost-free models). | |
| 7 | Have you noticed weak cooling, water under the fridge or unusual noise? | No / Weak cooling / Water leaking / Unusual noise | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the fridge before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the fridge yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Use a stabilizer of the right rating if the power at home is unsteady. | HIGH | power_issues = Often or Sometimes | Voltage swings can damage the compressor and the control board. | |
| 4 | Keep the door seal clean and check it closes firmly all round. | MEDIUM | door_seal = Not always or No | A good seal keeps the cold in. | |
| 5 | Leave space behind and beside the fridge for air to flow. | MEDIUM | wall_gap = Very little | Trapped heat makes the compressor run longer. | |
| 6 | Leave gaps between items so cold air can move. | LOW | load = Packed tight | Air needs room to cool everything evenly. | |
| 7 | If thick ice builds up, follow your manual's defrost steps or contact the brand's service. | MEDIUM | defrost = Thick ice | Thick ice reduces cooling. | |
| 8 | If cooling gets weak, water collects under the fridge or new noises start, contact the brand's service. | HIGH | symptoms = Weak cooling or Water leaking or Unusual noise | Small cooling faults can spoil food and grow into bigger repairs. | |
| 9 | Let hot food cool down before putting it in. | LOW | always | Hot food makes the fridge work harder. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Wipe the fridge door seal and check it closes firmly. | about once a month | Check your manual for the interval for your model. | |
| Ask for the coils at the back to be checked and dusted at a service visit. | about once a year | Check your manual and warranty card for service advice. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| power_issues = Often | raise | Frequent power dips or surges can damage the compressor. | |
| surge = Yes | lower | A stabilizer protects against unsteady power. | |
| door_seal = No or Not always | raise | A poor seal makes the compressor run longer. | |
| wall_gap = Very little | raise | Trapped heat makes the compressor work harder. | |
| symptoms = Weak cooling or Water leaking or Unusual noise | raise | These are early signs of a fault. | |

### Usual warranty structure (no numbers)

- **Whole fridge:** Covered for a standard period - check your warranty card.
- **Compressor:** Often has its own, separate period - check your warranty card.
- **Gas refill:** May be covered separately or only for a shorter time - check your warranty card.

### Exclusions to look for

- Damage from voltage fluctuations
- Plastic parts, shelves, trays and bulbs
- Rust or damage from moving the fridge
- Damage by rodents or insects
- Use in shops or commercial premises

## Room heater

Hazards: electric. Matches: room heater, oil heater, fan heater, halogen heater, radiator heater, heater.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many hours a day is the heater on? | Less than 3 hours / 3 to 6 hours / More than 6 hours | Long running heats parts and raises fire risk. | |
| 2 | Is it left on overnight or when nobody is in the room? | No / Sometimes / Yes | Unattended heaters are a fire risk. | |
| 3 | Is it kept away from curtains, bedding and furniture? | Yes / Not always | Things close to a heater can catch fire. | |
| 4 | Is it plugged into an extension board? | No, a wall socket / Yes | Heaters draw a lot of power and can overheat extension boards. | |
| 5 | Are there small children or pets in the home? | No / Yes | Hot surfaces can burn. | |
| 6 | Have you noticed a burning smell, sparks or the heater switching off by itself? | No / Burning smell / Sparks / Switches off by itself | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the heater before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the heater yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Safety: Don't bypass or tamper with the thermostat or any safety cut-out. | HIGH | always | These stop the appliance overheating; without them it can cause burns or a fire. | |
| 4 | Safety: Switch the heater off when you leave the room or go to sleep. | HIGH | overnight = Sometimes or Yes | Unattended heaters cause fires. | |
| 5 | Safety: Keep the heater well away from curtains, bedding and furniture. | HIGH | clearance = Not always | Fabric close to a heater can catch fire. | |
| 6 | Safety: Plug the heater straight into a wall socket of the right rating. | HIGH | extension = Yes | Extension boards can overheat under the load. | |
| 7 | Keep children and pets away from the heater. | MEDIUM | children_pets = Yes | Hot surfaces can burn. | |
| 8 | If you smell burning, see sparks or it keeps cutting out, unplug it and contact the brand's service. | HIGH | symptoms = Burning smell or Sparks or Switches off by itself | These can be signs of a dangerous fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Before winter, check the heater's cable and plug for damage (unplugged). | about once a year, before winter | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| overnight = Yes | raise | Unattended heaters are a fire risk. | |
| clearance = Not always | raise | Things close to the heater can catch fire. | |
| extension = Yes | raise | Extension boards can overheat. | |
| hours_per_day = More than 6 hours | raise | Long running heats parts. | |
| symptoms = Burning smell or Sparks or Switches off by itself | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Heater:** Covered for a standard period - check your warranty card.
- **Heating element:** Some brands cover the element separately - check your warranty card.

### Exclusions to look for

- Damage from voltage fluctuations
- Misuse, such as covering the heater or drying clothes on it
- Burn marks and plastic damage
- Halogen tubes and other consumable parts

## Smartphone

Hazards: electric, battery. Matches: smartphone, mobile phone, mobile, phone, iphone, 5g.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | Which charger is usually used? | The one it came with / Another branded charger / A cheap or unbranded one / Whatever is around | Poor or mismatched chargers are a common cause of battery and port damage. | |
| 2 | Is the phone usually charged overnight or in a hot place? | No / Overnight / In a hot place, like a car or in the sun | Heat and constant full charge age the battery faster. | |
| 3 | Does the phone have a case and a screen guard? | Both / One of them / Neither | They take the knocks that crack screens. | |
| 4 | Has the phone been dropped hard in the last few months? | No / Once / Several times | Drops can damage the screen and inner parts even without visible cracks. | |
| 5 | Has the phone been near water, rain or a spill? | No / A splash / It got wet | Water damage is usually not covered. | |
| 6 | Are software updates installed? | Yes / Sometimes / No | Updates fix bugs and security problems. | |
| 7 | Have you noticed the battery swelling, the phone getting very hot or draining fast? | No / Battery or back swelling / Very hot / Draining fast | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Stop using the phone and keep it away from anything that can burn if the battery swells, gets very hot or smells unusual. | HIGH | always | A damaged battery can catch fire. | |
| 2 | Safety: Don't open, puncture or crush the battery, and don't use it after a hard fall that dented it. | HIGH | always | Damaged battery cells can overheat or catch fire. | |
| 3 | Safety: Switch the phone off and unplug the charger before cleaning it. | HIGH | always | Cleaning a charging device risks a short circuit. | |
| 4 | Charge with the charger it came with or another certified one. | HIGH | charger = A cheap or unbranded one or Whatever is around | Poor chargers can damage the battery and the charging port. | |
| 5 | Avoid charging or leaving the phone in hot places such as a car or in direct sun. | MEDIUM | overnight = In a hot place, like a car or in the sun | Heat ages the battery faster. | |
| 6 | Use a case and a screen guard. | MEDIUM | case_guard = One of them or Neither | They protect against the drops that crack screens. | |
| 7 | Keep the phone away from water; if it gets wet, switch it off and contact the brand's service. | MEDIUM | water = A splash or It got wet | Water damage is usually not covered and spreads if the phone stays on. | |
| 8 | Install software updates when offered. | LOW | updates = Sometimes or No | Updates fix bugs and security problems. | |
| 9 | If the battery drains fast or the phone runs very hot, contact the brand's service. | HIGH | symptoms = Very hot or Draining fast | These can be signs of a battery problem. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Back up your phone's photos and contacts. | about once a month | Check your manual or phone settings for automatic backup. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| charger = A cheap or unbranded one or Whatever is around | raise | Poor chargers can damage the battery. | |
| overnight = In a hot place, like a car or in the sun | raise | Heat ages the battery faster. | |
| case_guard = Both | lower | A case and screen guard protect against drops. | |
| drops = Several times | raise | Repeated drops can damage inner parts. | |
| water = It got wet | raise | Water can cause damage that shows up later. | |
| symptoms = Battery or back swelling or Very hot or Draining fast | raise | These can be signs of a battery fault. | |

### Usual warranty structure (no numbers)

- **Phone:** Covered for a standard period - check your warranty card.
- **Battery:** Often covered for a shorter period - check your warranty card.
- **Charger, cable and earphones:** Accessories often have a shorter period - check your warranty card.

### Exclusions to look for

- Physical damage, including a cracked screen
- Liquid damage
- Repairs by people the brand has not authorised
- Damage from chargers or accessories that are not genuine
- Software changes such as rooting

## Smartwatch or fitness band

Hazards: electric, battery. Matches: smartwatch, smart watch, fitness band, smart band, fitness tracker, watch.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | Which charger is used? | Its own charger / Another charger | Poor chargers can damage the small battery. | |
| 2 | Is it worn while swimming, showering or in a sauna? | No / Swimming / Shower or sauna | Water resistance has limits, and hot water and steam are harsher. | |
| 3 | Is it worn during heavy exercise? | Rarely / Often | Sweat on the sensors and contacts causes problems. | |
| 4 | How often are the sensors and strap cleaned? | About once a week / Rarely | Dirt gives wrong readings and stops charging. | |
| 5 | Are watch and app updates installed? | Yes / No | Updates fix bugs. | |
| 6 | Have you noticed it not charging, draining fast, a swollen back or water inside? | No / Not charging / Draining fast / Swollen back / Water inside | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Stop using the watch and keep it away from anything that can burn if the battery swells, gets very hot or smells unusual. | HIGH | always | A damaged battery can catch fire. | |
| 2 | Safety: Don't open, puncture or crush the battery, and don't use it after a hard fall that dented it. | HIGH | always | Damaged battery cells can overheat or catch fire. | |
| 3 | Safety: Switch the watch off and unplug the charger before cleaning it. | HIGH | always | Cleaning a charging device risks a short circuit. | |
| 4 | Charge it only with its own charger. | HIGH | charger = Another charger | The wrong charger can damage the battery. | |
| 5 | Check your manual before swimming or showering with it, and avoid saunas and hot water. | MEDIUM | water_use = Swimming or Shower or sauna | Water resistance has limits and weakens with age. | |
| 6 | Wipe the sensors, contacts and strap regularly. | LOW | cleaning = Rarely; sweat = Often | Dirt gives wrong readings and stops charging. | |
| 7 | Install updates for the watch and its app. | LOW | updates = No | Updates fix bugs. | |
| 8 | If it stops charging or water gets inside, contact the brand's service. | MEDIUM | symptoms = Not charging or Draining fast or Water inside | These can be signs of a fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Clean the watch's sensors, contacts and strap. | about once a week | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| charger = Another charger | raise | The wrong charger can damage the battery. | |
| water_use = Shower or sauna | raise | Hot water and steam can get past the seals. | |
| cleaning = About once a week | lower | Clean contacts charge reliably. | |
| symptoms = Not charging or Draining fast or Swollen back or Water inside | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Watch or band:** Covered for a standard period - check your warranty card.
- **Strap and charger:** Often covered for a shorter time or not at all - check your warranty card.

### Exclusions to look for

- Water damage beyond the stated water resistance
- Physical damage, including a cracked screen
- Straps and charging cables
- Battery wear

## Speaker or soundbar

Hazards: electric, battery. Matches: soundbar, sound bar, speaker, bluetooth speaker, home theatre, home theater, party speaker.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | What kind is it? | Portable, with a battery / Mains-powered soundbar or speaker | Battery speakers and mains soundbars need different care. | |
| 2 | Is it often played at full volume for long? | No / Yes | Long full-volume play strains the speakers and amplifier. | |
| 3 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 4 | Is it used outdoors, near water or in the rain? | No / Sometimes | Water and dust can get in, even with some water resistance. | |
| 5 | Is there space around it for air? | Yes / No | Amplifiers warm up and need air. | |
| 6 | Have you noticed crackling, distortion, it not charging or switching off? | No / Crackling or distortion / Not charging / Switches off | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: If a portable speaker's battery swells or gets very hot, stop using it and keep it away from anything that can burn. | HIGH | always | A damaged battery can catch fire. | |
| 2 | Safety: Switch off and unplug the speaker before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 3 | Safety: Don't open the speaker yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 4 | Avoid long stretches at full volume. | MEDIUM | volume = Yes | This strains the speakers and amplifier. | |
| 5 | Plug a mains soundbar into a surge protector. | MEDIUM | power_issues = Often or Sometimes | Power spikes can damage the amplifier. | |
| 6 | Keep it away from water and bring it inside after outdoor use. | LOW | outdoors = Sometimes | Water and dust can get in. | |
| 7 | Leave space around it. | LOW | ventilation = No | Amplifiers need air to stay cool. | |
| 8 | If it crackles at normal volume or keeps switching off, contact the brand's service. | MEDIUM | symptoms = Crackling or distortion or Not charging or Switches off | These can be signs of a fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Dust the speaker grilles and vents (switched off). | about once a month | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| volume = Yes | raise | Long full-volume play strains the speakers. | |
| power_issues = Often | raise | Power spikes can damage the amplifier. | |
| outdoors = Sometimes | raise | Water and dust can get in. | |
| symptoms = Crackling or distortion or Not charging or Switches off | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Speaker or soundbar:** Covered for a standard period - check your warranty card.
- **Battery and remote:** Often covered for a shorter time - check your warranty card.

### Exclusions to look for

- Speaker damage from very loud use
- Water or dust damage beyond the stated rating
- Remote controls and cables
- Damage from power surges

## Tablet

Hazards: electric, battery. Matches: tablet, ipad, tab.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | Which charger is usually used? | The one it came with / Another branded charger / A cheap or unbranded one / Whatever is around | Poor or mismatched chargers are a common cause of battery and port damage. | |
| 2 | Does the tablet have a case and a screen guard? | Both / One of them / Neither | They take the knocks that crack screens. | |
| 3 | Is it mostly used by children? | No / Yes | Drops and spills are more common with young users. | |
| 4 | Is it often charged or left in hot places? | No / Yes | Heat ages the battery faster. | |
| 5 | Has it been dropped hard in the last few months? | No / Once / Several times | Drops can damage inner parts even without visible cracks. | |
| 6 | Have you noticed the battery swelling, the tablet getting very hot or draining fast? | No / Swelling / Very hot / Draining fast | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Stop using the tablet and keep it away from anything that can burn if the battery swells, gets very hot or smells unusual. | HIGH | always | A damaged battery can catch fire. | |
| 2 | Safety: Don't open, puncture or crush the battery, and don't use it after a hard fall that dented it. | HIGH | always | Damaged battery cells can overheat or catch fire. | |
| 3 | Safety: Switch the tablet off and unplug the charger before cleaning it. | HIGH | always | Cleaning a charging device risks a short circuit. | |
| 4 | Charge with the charger it came with or another certified one. | HIGH | charger = A cheap or unbranded one or Whatever is around | Poor chargers can damage the battery. | |
| 5 | Use a sturdy case and a screen guard. | MEDIUM | case_guard = One of them or Neither; children = Yes | They protect against drops. | |
| 6 | Avoid charging or leaving the tablet in hot places. | MEDIUM | heat = Yes | Heat ages the battery faster. | |
| 7 | Clean the screen with a soft dry cloth and no sprays. | LOW | always | Liquids can seep in and damage the screen. | |
| 8 | Install software updates when offered. | LOW | always | Updates fix bugs and security problems. | |
| 9 | If it runs very hot or drains fast, contact the brand's service. | HIGH | symptoms = Very hot or Draining fast | These can be signs of a battery problem. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Back up the photos and files on your tablet. | about once a month | Check your manual or device settings for automatic backup. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| charger = A cheap or unbranded one or Whatever is around | raise | Poor chargers can damage the battery. | |
| case_guard = Both | lower | A case and screen guard protect against drops. | |
| children = Yes | raise | Drops and spills are more common. | |
| drops = Several times | raise | Repeated drops can damage inner parts. | |
| symptoms = Swelling or Very hot or Draining fast | raise | These can be signs of a battery fault. | |

### Usual warranty structure (no numbers)

- **Tablet:** Covered for a standard period - check your warranty card.
- **Battery:** Often covered for a shorter period - check your warranty card.
- **Charger and accessories:** Often covered separately - check your warranty card.

### Exclusions to look for

- Physical damage, including a cracked screen
- Liquid damage
- Repairs by people the brand has not authorised
- Damage from chargers that are not genuine

## Television

Hazards: electric. Matches: television, smart tv, led tv, oled, qled, tv.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many hours a day is the TV on? | Less than 4 hours / 4 to 8 hours / More than 8 hours | Long daily use wears the panel and backlight. | |
| 2 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 3 | Is it plugged into a surge protector or stabilizer? | Yes / No / Not sure | These protect against power spikes. | |
| 4 | How is the TV placed? | Wall-mounted by a technician / On its stand / Wall-mounted by someone else / On an unsteady surface | A firm mount or stand prevents falls that break the panel. | |
| 5 | Is there space around the back and sides of the TV? | Yes / It is in a tight cabinet | A television needs air around it to stay cool. | |
| 6 | Are there small children or pets near the TV? | No / Yes | Bumps and pulled cables are a common cause of broken panels. | |
| 7 | Have you noticed lines on the screen, flicker or no sound? | No / Lines or patches / Flicker / Sound problems | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the TV before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the TV yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Plug the TV into a surge protector, and unplug it during lightning storms. | HIGH | power_issues = Often or Sometimes; surge = No or Not sure | Power surges are a common cause of TV failures. | |
| 4 | Clean the screen with a soft dry cloth and no sprays or strong cleaners. | MEDIUM | always | Liquids and chemicals can damage the screen coating. | |
| 5 | Make sure the TV is firmly mounted or on a stable stand. | HIGH | mounting = Wall-mounted by someone else or On an unsteady surface; children_pets = Yes | A fall can break the panel. | |
| 6 | Leave space around the TV for air to flow. | MEDIUM | ventilation = It is in a tight cabinet | Heat shortens the life of the electronics. | |
| 7 | If lines, patches, flicker or sound problems appear, contact the brand's service. | MEDIUM | symptoms = Lines or patches or Flicker or Sound problems | Early checks can find faults while the warranty applies. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Dust the TV's vents and the area around it (switched off and unplugged). | about once a month | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| hours_per_day = More than 8 hours | raise | Long daily use wears the panel and backlight. | |
| power_issues = Often | raise | Power surges can damage the electronics. | |
| surge = Yes | lower | A surge protector guards against power spikes. | |
| mounting = On an unsteady surface or Wall-mounted by someone else | raise | An insecure TV can fall and break. | |
| symptoms = Lines or patches or Flicker or Sound problems | raise | These are early signs of a fault. | |

### Usual warranty structure (no numbers)

- **Whole TV:** Covered for a standard period - check your warranty card.
- **Display panel:** Some brands cover the panel for a different period - check your warranty card.
- **Remote and accessories:** Often covered for a shorter time or not at all - check your warranty card.

### Exclusions to look for

- Physical damage to the screen, including cracks
- Damage from power surges or lightning
- Damage from wall mounting not done by the brand's technician
- Liquid damage
- Remote controls and batteries

## Vacuum or robot vacuum

Hazards: electric, battery. Matches: vacuum cleaner, robot vacuum, robotic vacuum, vacuum, wet and dry vacuum.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | What kind of vacuum is it? | Corded / Cordless (battery) / Robot | Corded, cordless and robot vacuums need different care. | |
| 2 | How many times a week is it used? | Less than 3 / 3 to 7 / More than 7 | Heavy use fills filters and wears brushes faster. | |
| 3 | How often are the bin and filter emptied and cleaned? | After each use / About once a week / Rarely | A full bin or dirty filter strains the motor. | |
| 4 | Is it ever used to pick up water or wet dirt? | No / Yes, it is a wet-and-dry model / Yes, but it is not a wet-and-dry model | Only wet-and-dry models can take liquid. | |
| 5 | Are hair and threads cleared from the brush? | Yes / Rarely | Tangled brushes strain the motor. | |
| 6 | Have you noticed weak suction, a burning smell or the battery not charging? | No / Weak suction / Burning smell / Battery not charging | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: If the battery swells, gets very hot or smells unusual, stop using the vacuum and keep it away from anything that can burn. | HIGH | always | A damaged battery can catch fire. | |
| 2 | Safety: Switch off and unplug the vacuum (or switch it off and remove it from the dock) before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 3 | Safety: Don't open the vacuum or its battery yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 4 | Don't pick up water or wet dirt unless it is a wet-and-dry model. | HIGH | wet_pickup = Yes, but it is not a wet-and-dry model | Liquid can damage the motor and cause a shock. | |
| 5 | Empty the bin and clean the filter as the manual describes. | MEDIUM | bin_filter = Rarely | A full bin or dirty filter strains the motor. | |
| 6 | Clear hair and threads from the brush (switched off). | MEDIUM | brush = Rarely | Tangled brushes strain the motor. | |
| 7 | Charge it only with its own charger or dock. | MEDIUM | kind = Cordless (battery) or Robot | The wrong charger can damage the battery. | |
| 8 | If suction gets weak after cleaning the filter, or it smells of burning, contact the brand's service. | MEDIUM | symptoms = Weak suction or Burning smell or Battery not charging | These can be signs of a motor fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Clean the vacuum's filter and brush (switched off). | about every 2 weeks with regular use | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| uses_per_week = More than 7 | raise | Heavy use wears the motor and brushes. | |
| bin_filter = Rarely | raise | A full bin strains the motor. | |
| wet_pickup = Yes, but it is not a wet-and-dry model | raise | Liquid can damage the motor. | |
| brush = Rarely | raise | Tangled brushes strain the motor. | |
| symptoms = Weak suction or Burning smell or Battery not charging | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Vacuum:** Covered for a standard period - check your warranty card.
- **Battery:** Often covered for a shorter period - check your warranty card.
- **Filters, brushes and bags:** Usually consumables, not covered - check your warranty card.

### Exclusions to look for

- Filters, brushes, bags and other consumables
- Damage from picking up liquids with a dry vacuum
- Battery wear
- Damage from chargers that are not genuine

## Voltage stabilizer

Hazards: electric. Matches: stabilizer, stabiliser, voltage stabilizer, servo stabilizer.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | Which appliance does it protect? | An AC / A fridge / A TV / Something else | The stabilizer must be rated for that appliance. | |
| 2 | Was the stabilizer chosen for that appliance's rating? | Yes / Not sure | An undersized stabilizer overheats. | |
| 3 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 4 | Where is it placed? | In an open place / Behind furniture or in a closed space | It needs air around it to stay cool. | |
| 5 | Does it click often or show high or low warnings? | Rarely / Often | Frequent switching means the supply swings a lot. | |
| 6 | Have you noticed a burning smell, humming or it getting very hot? | No / Burning smell / Loud humming / Very hot | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off the mains supply before cleaning or moving the stabilizer. | HIGH | always | It carries mains voltage. | |
| 2 | Safety: Don't open the stabilizer yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Use a stabilizer rated for the appliance it protects. | HIGH | rating = Not sure | An undersized stabilizer overheats and gives poor protection. | |
| 4 | Keep space around it for air to flow. | MEDIUM | placement = Behind furniture or in a closed space | It warms up while working. | |
| 5 | Keep it free of dust (switched off). | LOW | always | Dust traps heat. | |
| 6 | If it switches very often, ask an electrician or your supplier to check the supply. | MEDIUM | clicking = Often; power_issues = Often | Large swings strain it and your appliance. | |
| 7 | If it smells of burning or gets very hot, switch it off and contact the brand's service. | HIGH | symptoms = Burning smell or Loud humming or Very hot | These can be signs of a dangerous fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Check the stabilizer's cable and plug, and dust it (switched off). | about every 3 months | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| rating = Not sure | raise | An undersized stabilizer overheats. | |
| power_issues = Often | raise | Large swings strain it. | |
| placement = Behind furniture or in a closed space | raise | Trapped heat shortens its life. | |
| symptoms = Burning smell or Loud humming or Very hot | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Stabilizer:** Covered for a standard period - check your warranty card.

### Exclusions to look for

- Damage from overloading or the wrong rating
- Damage from lightning or extreme surges
- Physical damage

## Washing machine

Hazards: electric. Matches: washing machine, washer, front load, top load, semi automatic, fully automatic, washer dryer.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | How many washes does it run in a week? | Fewer than 4 / 4 to 8 / More than 8 | More washes mean more wear on the motor, drum bearings and belts. | |
| 2 | Is the drum usually filled to the top? | No, about three-quarters / Sometimes / Yes, usually full | Overloading strains the motor and bearings. | |
| 3 | Does the machine shake or move during the spin? | No / A little / A lot | An unlevel machine shakes and wears faster. | |
| 4 | How often is the lint or drain filter cleaned? | About once a month / Rarely / Never / don't know where it is | A blocked filter slows draining and spoils washes. | |
| 5 | Does your water leave white marks on taps and buckets? | No / Some / A lot | Hard water leaves scale that affects heating and the drum. | |
| 6 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 7 | Have you noticed leaks, a burning smell, error codes or water not draining? | No / Leaks / Error codes / Not draining | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the washing machine before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the washing machine yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Fill the drum to about three-quarters, not to the top. | HIGH | overload = Sometimes or Yes, usually full | Overloading strains the motor and drum bearings. | |
| 4 | Keep the machine level and on a firm floor. | MEDIUM | level = A little or A lot | A level machine shakes less and lasts longer. | |
| 5 | Clean the lint or drain filter as your manual describes. | MEDIUM | filter_cleaning = Rarely or Never / don't know where it is; loads_per_week = More than 8 | A clean filter helps the water drain. | |
| 6 | Leave the door or lid open after a wash so the inside can dry. | LOW | always | This stops smells and mould on the seal. | |
| 7 | In hard-water areas, run a drum clean cycle as your manual suggests. | LOW | water_hard = Some or A lot | Scale builds up on the heater and drum. | |
| 8 | Use a stabilizer or surge protector if the power is unsteady. | MEDIUM | power_issues = Often or Sometimes | Power swings can damage the control board. | |
| 9 | If it leaks, smells burnt, shows error codes or stops draining, switch it off and contact the brand's service. | HIGH | symptoms = Leaks or Error codes or Not draining | Running it with a fault can make the damage worse. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Clean the washing machine's lint or drain filter. | about once a month | Check your manual for the interval for your model. | |
| Run a drum clean or empty hot wash. | about once a month | Check your manual for the interval for your model. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| loads_per_week = More than 8 | raise | Heavy use wears the motor and bearings faster. | |
| overload = Yes, usually full | raise | Overloading strains the motor and bearings. | |
| level = A lot | raise | A shaking machine wears faster. | |
| filter_cleaning = Never / don't know where it is | raise | A blocked filter strains the drain pump. | |
| water_hard = A lot | raise | Hard water leaves scale on the heater. | |
| symptoms = Leaks or Error codes or Not draining | raise | These are early signs of a fault. | |

### Usual warranty structure (no numbers)

- **Whole machine:** Covered for a standard period - check your warranty card.
- **Motor:** Often has its own, longer period - check your warranty card.
- **Drum, PCB and other parts:** Some brands cover these separately - check your warranty card.

### Exclusions to look for

- Damage from voltage fluctuations
- Damage from hard water or scale
- Rubber parts, hoses and plastic parts
- Damage by rodents
- Installation by people the brand has not authorised
- Use in laundries or commercial premises

## Water heater / geyser

Hazards: electric, gas. Matches: geyser, water heater, instant heater, storage heater, gas geyser.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | What kind of water heater is it? | Electric, with a tank / Electric, instant / Gas | Electric and gas heaters need different safety steps. | |
| 2 | Does your water leave white marks on taps and buckets? | No / Some / A lot | Hard water builds scale on the tank and heating element. | |
| 3 | How long is it usually left switched on? | Only when needed / A few hours / Always on | Leaving it on for hours wastes power and keeps parts hot. | |
| 4 | Was it installed with proper earthing and the safety valve fitted? | Yes / Not sure / No | Earthing and the pressure valve protect against shocks and pressure build-up. | |
| 5 | When was it last serviced or descaled? | Within the last year / More than a year ago / Never | Regular service removes scale and checks the safety parts. | |
| 6 | Have you noticed leaks, tripping, rusty water or a smell of burning or gas? | No / Leaks / Tripping / Rusty water / A burning or gas smell | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off the water heater at the wall before cleaning it. | HIGH | always | Cleaning it while it is on risks an electric shock. | |
| 2 | Safety: Don't open the water heater yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Safety: Don't bypass or tamper with the thermostat or any safety cut-out. | HIGH | always | These stop the appliance overheating; without them it can cause burns or a fire. | |
| 4 | Safety: If you smell gas: close the gas supply, don't switch anything electrical on or off, open doors and windows to ventilate, and call your gas or service number from outside. | HIGH | always | A spark in a room full of gas can cause an explosion. | |
| 5 | Have the earthing and safety valve checked by the brand's authorised technician. | HIGH | earthing = Not sure or No | These protect against shocks and dangerous pressure. | |
| 6 | Switch it on only when you need hot water. | MEDIUM | hours_on = A few hours or Always on | This saves power and reduces wear. | |
| 7 | In hard-water areas, book descaling at a service visit. | MEDIUM | water_hard = Some or A lot; last_service = More than a year ago or Never | Scale makes the heating element work harder. | |
| 8 | If it leaks, trips, gives rusty water or smells of burning or gas, switch it off and contact the brand's service. | HIGH | symptoms = Leaks or Tripping or Rusty water or A burning or gas smell | These can be signs of a dangerous fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Book a water heater service and descaling check. | about once a year | Check your manual and warranty card for the recommended service schedule. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| water_hard = A lot | raise | Hard water builds scale on the tank and element. | |
| hours_on = Always on | raise | Being always on keeps parts hot for longer. | |
| earthing = No or Not sure | raise | Without proper earthing or a safety valve the heater is less safe. | |
| last_service = Within the last year | lower | A recent service catches problems early. | |
| symptoms = Leaks or Tripping or Rusty water or A burning or gas smell | raise | These are early signs of a fault. | |

### Usual warranty structure (no numbers)

- **Whole heater:** Covered for a standard period - check your warranty card.
- **Inner tank:** Often has its own, longer period - check your warranty card.
- **Heating element:** Often has its own period - check your warranty card.

### Exclusions to look for

- Damage from hard water, scale or sediment
- Installation without the safety valve or proper earthing
- The anode rod and other consumable parts
- Damage from voltage fluctuations
- Installation by people the brand has not authorised

## Water purifier

Hazards: electric. Matches: water purifier, ro purifier, uv purifier, ro+uv, purifier.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | Is your water source a borewell, tanker or municipal supply? | Municipal / Borewell or tanker / Not sure | Hard or salty water wears the membrane faster. | |
| 2 | Roughly how much purified water is used each day? | Less than 10 litres / 10 to 25 litres / More than 25 litres | Heavy use wears the filters faster. | |
| 3 | When were the filters or membrane last changed? | Within 6 months / 6 to 12 months ago / More than a year ago / Never | Old filters stop cleaning the water well. | |
| 4 | Has the taste or smell of the water changed? | No / Yes | A change can mean the filters need attention. | |
| 5 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 6 | Have you noticed leaks, slow flow or the purifier running non-stop? | No / Leaks / Slow flow / Runs non-stop | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the purifier before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the purifier yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Have the filters and membrane changed by the brand's service on schedule. | HIGH | filter_change = More than a year ago or Never; taste = Yes | Old filters stop cleaning the water properly. | |
| 4 | If your water is hard or from a borewell, ask the brand's service about the right settings and service interval. | MEDIUM | tds = Borewell or tanker | Hard water wears the membrane faster. | |
| 5 | Use a surge protector if the power is unsteady. | MEDIUM | power_issues = Often | Power swings can damage the pump and UV lamp. | |
| 6 | Ask for the storage tank to be cleaned at service visits. | LOW | always | A clean tank keeps the water safe. | |
| 7 | If it leaks, the flow slows or it runs non-stop, switch it off and contact the brand's service. | HIGH | symptoms = Leaks or Slow flow or Runs non-stop | Leaks and non-stop running can damage the pump. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Book a water purifier service and filter check. | about every 6 months | Check your manual and warranty card for the recommended filter schedule. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| tds = Borewell or tanker | raise | Hard water wears the membrane faster. | |
| litres_per_day = More than 25 litres | raise | Heavy use wears the filters faster. | |
| filter_change = Within 6 months | lower | Fresh filters work properly. | |
| filter_change = More than a year ago or Never | raise | Old filters stop working well. | |
| symptoms = Leaks or Slow flow or Runs non-stop | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Purifier:** Covered for a standard period - check your warranty card.
- **Filters, membrane and UV lamp:** Usually consumables, not covered - check your warranty card.

### Exclusions to look for

- Filters, membranes, UV lamps and other consumables
- Damage from very hard or untreated water
- Damage from voltage fluctuations
- Installation by people the brand has not authorised

## Wi-Fi router

Hazards: electric. Matches: router, wi-fi router, wifi router, mesh, modem, wifi.

### Questions (asked 3 at a time; every question has Skip)

| # | Question | Answers | Why we ask | Approve |
|---|---|---|---|---|
| 1 | Where is the router placed? | In an open spot / In a cabinet or behind things | Routers run warm and need air; placement also affects coverage. | |
| 2 | Which power adapter is used? | The one it came with / Another adapter | The wrong adapter can damage the router. | |
| 3 | Does the power at home often dip, flicker or trip? | Often / Sometimes / Rarely | Unsteady power can damage the electronics. | |
| 4 | Is the router's firmware updated? | Yes, or it updates itself / No / Not sure | Updates fix bugs and security holes. | |
| 5 | Has the default admin password been changed? | Yes / No / Not sure | Default passwords are easy to guess. | |
| 6 | Have you noticed frequent drops, restarts or the router getting hot? | No / Frequent drops / Restarts by itself / Gets hot | Early signs let you get it checked before a small fault grows. | |

### Care tips (safety first, then by priority)

| # | Tip | Priority | Shown when | Why | Approve |
|---|---|---|---|---|---|
| 1 | Safety: Switch off and unplug the router before cleaning it. | HIGH | always | Cleaning an appliance that is plugged in risks an electric shock. | |
| 2 | Safety: Don't open the router yourself; leave repairs to the brand's authorised service. | HIGH | always | Inside there are live parts, and opening it can also end the warranty. | |
| 3 | Keep the router in an open spot with air around it. | MEDIUM | placement = In a cabinet or behind things | Heat causes drops and restarts. | |
| 4 | Use the adapter it came with. | HIGH | adapter = Another adapter | The wrong adapter can damage the router. | |
| 5 | Plug it into a surge protector. | MEDIUM | power_issues = Often or Sometimes | Power spikes can damage network equipment. | |
| 6 | Keep the firmware updated. | MEDIUM | updates = No or Not sure | Updates fix bugs and security holes. | |
| 7 | Change the default admin password. | MEDIUM | password = No or Not sure | Default passwords are easy to guess. | |
| 8 | If it keeps restarting or runs hot, contact the brand's or your internet provider's support. | LOW | symptoms = Restarts by itself or Gets hot | These can be signs of a fault. | |

### Maintenance reminders

| Reminder | Interval | Note | Approve |
|---|---|---|---|
| Check for router firmware updates. | about every 3 months | Check your manual or the router's app. | |

### Risk factors

| Answer | Effect | Reason | Approve |
|---|---|---|---|
| placement = In a cabinet or behind things | raise | Heat causes drops and restarts. | |
| adapter = Another adapter | raise | The wrong adapter can damage it. | |
| power_issues = Often | raise | Power spikes can damage it. | |
| symptoms = Restarts by itself or Gets hot | raise | These are signs of a fault. | |

### Usual warranty structure (no numbers)

- **Router:** Covered for a standard period - check your warranty card.
- **Adapter:** May be covered separately - check your warranty card.

### Exclusions to look for

- Damage from power surges or lightning
- Damage from the wrong adapter
- Physical damage
