# ffxiv-prog-visualizer
A python script to visualize how your pulls have progressed for a specific raid.

# Overview
The script will comb over your public FFLogs reports that belong to a given zone (by default, The Epic of Alexander) and compile them into a somewhat interesting chart.

## Example output
![output](https://user-images.githubusercontent.com/2066575/174406582-c35b4ddd-88a2-4c11-be75-ac149d03308c.png)
# Caveats
- It does not discriminate between reports from your guild, or public reports. _All_ public personal reports will be consumed. A way around this is by privating specific reports, but that's quite annoying.
# Usage
This section assumes you have an FFLogs account, preferably with some pulls for a given encounter uploaded.

By default, the zone id of The Epic of Alexander will be used, which is `32`. Feel free to change this in `constants.py` to any other zone ID, if you'd like -- for example, Dragonsong's Reprise is `45`.

### Updating config.ini
1. Copy `sample-config.ini` to a new file named `config.ini`. We'll be populating each field as we go.
2. Create an FFLogs API client by following the docs here: https://www.fflogs.com/api/docs. Set the `client_id` and `client_secret` in `config.ini` to your FFLogs client ID and secret.
3. Navigate to your personal reports in FFLogs. Your user id will be in the URL. For example, https://www.fflogs.com/user/reports-list/123456/ indicates that your user id is 123456. Set `fflogs_user_id` in your `config.ini` to this value.

### Running the script on your machine
1. (Optional) Install the Liberation Serif font in `resources`, or by [finding it online](https://www.fontsquirrel.com/fonts/liberation-serif). If not installed, the output will default to DejaVu Sans.
2. Make sure you have [Python 3.10](https://www.python.org/downloads/release/python-3100/) installed (haven't tried with older versions, I'm sure some of them work).
3. Install requirements: `pip install -r requirements.txt`.
4. `python main.py`. It will automatically generate an FFLogs API token and populate your `config.ini` with it.

### Running the script via Docker Compose
1. `docker-compose build prog`
2. `docker-compose run prog`

### How do I change the progress markers on the chart?
Currently, the progress indicators set are for The Epic of Alexander. They are set in `main.py` near the end of the `main` method. The only types of progress indicators currently supported are by ability cast (e.g. "we just hit enrage (any boss)", or "we saw Advanced Relativity (E12S)", or by the encounter ending.

TEA progress indicators in code:
```python
    progress_indicators = [
        AbilityProgressIndicator(index=0, label='Living Liquid', ability_ids={18864}, style={'color': 'lightskyblue'}),
        AbilityProgressIndicator(index=1, label='Limit Cut', ability_ids={18480}, style={'color': 'dodgerblue'}),
        AbilityProgressIndicator(index=2, label='BJ/CC', ability_ids={18516}, style={'color': 'orange'}),
        AbilityProgressIndicator(index=3, label='Alexander Prime', ability_ids={18522, 19075}, style={'color': 'silver'}),  # Post Wormhole -- Mega Holy
        AbilityProgressIndicator(index=4, label='Wormhole Formation', ability_ids={18542}, style={'color': 'black'}),
        AbilityProgressIndicator(index=5, label='Post-Wormhole Alex', ability_ids={19075}, style={'color': 'red'}),  # Post Wormhole -- Mega Holy
        AbilityProgressIndicator(index=6, label='Perfect Alexander', ability_ids={18557}, style={'color': 'white', 'mec': 'black', 'marker': '8'}),
        AbilityProgressIndicator(index=7, label='T̴̼͚̕Ê̵͇͙̲M̵̧̛͖̓̍̌̆̀͛̚͝P̷̻̍̉͆̄̃̌̍͊̕O̶̺̳͍̬̰͉̬̤͑̃̀͗͆͗͌̌̓̇̅͜͠R̷͈̺͓̥̭͉͍͗A̷̫̪͖̰̞͙̫̭̜͇͆͌́̆͋͒͂̕̕̚͜Ļ̶̧̛̟̥͚̺̣̗̼̬̲̋̌̍̓ ̷̙͌̓̐̈́̓̅͛P̷̟̬̬̜̳͛̀͑̅̓͊̾͌͑͌͘Ṟ̵̛͎͕̹̮̜͊̆̋͒͛̄̔͌͠͝͝Ǐ̴̛̮̱͎̼͎͈̙̮͎̫̱͌̌̒̈́̚ͅS̴̛͖̰̗͓̈̈́̂̈̀̾̀̿̅͛͘Ơ̶̛͎̹͚̞̠̺̙̂̿̓͛̍́̋̎͝͝ͅŅ̶̨̹̯̖͚͙̌', ability_ids={18583}, style={'color': 'silver', 'mec': 'black', 'marker': '*', 'markersize': 12}),
        VictoryIndicator(index=8, label='Prey Slaughtered', style={'color': 'gold', 'mec': 'black', 'marker': '*', 'markersize': 12})
    ]
```

You can browse FFLogs or the FFLogs API to figure out which ability ID to use if you'd like to create a set of progress indicators for a different encounter. For example, a set of progress indicators for Dragonsong's Reprise could look like:

```python
    progress_indicators = [
        AbilityProgressIndicator(index=0, label='Trash', ability_ids={25300}, style={'color': 'lightskyblue'}),
        AbilityProgressIndicator(index=1, label='Thordan', ability_ids={25544}, style={'color': 'dodgerblue'}),
        AbilityProgressIndicator(index=2, label='Strength', ability_ids={25555}, style={'color': 'gold'}),
        AbilityProgressIndicator(index=3, label='Sanctity', ability_ids={25569}, style={'color': 'blue'}),
        AbilityProgressIndicator(index=4, label='Nidhogg', ability_ids={26376}, style={'color': 'purple'}),
        AbilityProgressIndicator(index=5, label='Eyes', ability_ids={26814}, style={'color': 'red'}),
        AbilityProgressIndicator(index=6, label='Intermission', ability_ids={25314}, style={'color': 'yellow'}),
        AbilityProgressIndicator(index=7, label='Wrath of the Heavens', ability_ids={27529}, style={'color': 'green'}),
        AbilityProgressIndicator(index=8, label='Death of the Heavens', ability_ids={27538}, style={'color': 'greenyellow'}),
        AbilityProgressIndicator(index=9, label='Double Dragons', ability_ids={27946}, style={'color': 'teal'}),
    ]
```

# Contributions
I most likely won't be updating this much anymore, but will be paying attention for issues/pull requests.
