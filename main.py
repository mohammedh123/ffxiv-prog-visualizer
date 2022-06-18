import argparse
import constants
import datetime
import functools
import imageio
import io
import itertools
import json
import logging
import matplotlib.patches as patches
import matplotlib.pyplot as plot
import pathlib
import pickle
import requests
import shelve
import sys

from abc import ABC, abstractmethod
from cache import JsonFileCache
from collections import defaultdict
from configparser import ConfigParser
from dataclasses import dataclass
from enum import Enum
from matplotlib.animation import FFMpegFileWriter
from matplotlib.ticker import FuncFormatter, MultipleLocator
from operator import itemgetter


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
    datefmt='%Y-%m-%d %H:%M:%S',
)


@dataclass
class ProgressIndicator(ABC):
    """Class for representing misc. information about the progress of a pull."""
    index: int
    label: str
    style: dict

    @abstractmethod
    def matches(self, token, cache, report, fight):
        raise NotImplementedError


@dataclass
class VictoryIndicator(ProgressIndicator):
    def matches(self, token, cache, report, fight):
        return fight['kill']


@dataclass
class AbilityProgressIndicator(ProgressIndicator):
    """Uses ability ids to indicate progress for a pull."""
    ability_ids: frozenset[int]

    def matches(self, token, cache, report, fight):
        cache_key = f'{report["code"]}-{fight["id"]}-{fight["startTime"]}-{fight["endTime"]}'
        if not (abilities_cast_by_enemies := cache.get(cache_key)):
            # These abilities are implicitly sorted in order of datetime by the FFLogs API
            abilities_cast_by_enemies = get_abilities_cast_by_enemies_by_report_and_fight(
                token, report['code'], fight['id'], fight['startTime'], fight['endTime'],
            )
            cache.set(cache_key, abilities_cast_by_enemies)

        # Look at the abilities cast in reverse order to get the latest progress indicating ability cast
        pull = None
        for ability_json in reversed(abilities_cast_by_enemies):
            if ability_json['abilityGameID'] in self.ability_ids:
                return True

        return False


@dataclass
class Pull:
    """Class for representing the basic information of a pull."""
    id: int
    report_id: str
    progress: ProgressIndicator
    duration_in_seconds: int


def get_new_token(client_id, client_secret):
    token_response = requests.post(
        constants.TOKEN_URL,
        data=constants.TOKEN_REQUEST_PAYLOAD,
        verify=False,
        allow_redirects=False,
        auth=(client_id, client_secret),
    )
    token_response_text = json.loads(token_response.text)
    return token_response_text['access_token']


def get_abilities(token):
    """
    Gets all the game ability ids and names.
    If abilities.json doesn't exist, it pulls directly from the fflogs api.
    Should only be pulled from the API once per patch.
    """
    abilities = []
    try:
        with open(constants.ABILITIES_FILENAME, 'r') as f:
            abilities = json.load(f)
    except:
        query_headers = {'Authorization': f'Bearer {token}'}
        current_page = 1
        has_more_pages = True
        abilities = []

        while has_more_pages:
            q = f"""query {{
                gameData {{
                    abilities(page: {current_page}) {{
                        data {{
                            id
                            name
                        }}
                        has_more_pages
                    }}
                }}
            }}"""
            try:
                r = requests.get(constants.API_URL, headers=query_headers, json={'query': q})
                response_json = json.loads(r.text)

                has_more_pages = response_json['data']['gameData']['abilities']['has_more_pages']
                abilities.extend(response_json['data']['gameData']['abilities']['data'])
            except Exception:
                logger.exception(f'Failed to get ability data. Response: {r.text}.')
                raise

            current_page += 1

        with open(constants.ABILITIES_FILENAME, 'w') as f:
            json.dump(abilities, f, separators=(',', ':'))

    return {d['id']: d['name'] for d in abilities}


def get_reports(token, user_id, zone_id):
    logger.info(f'Getting reports from FFLogs for user {user_id} and zone {zone_id}.')
    query_headers = {'Authorization': f'Bearer {token}'}

    current_page = 1
    has_more_pages = True
    reports = []
    limit = 50

    while has_more_pages:
        q = f"""query {{
            reportData {{
                reports(userID: {user_id}, zoneID: {zone_id}, limit: {limit}, page: {current_page}) {{
                    data {{
                        fights {{
                            id
                            encounterID
                            fightPercentage
                            startTime
                            endTime
                            kill
                        }}
                        code
                        startTime
                        endTime
                    }}
                    has_more_pages
                }}
            }}
        }}"""
        try:
            r = requests.get(constants.API_URL, headers=query_headers, json={'query': q})
            response_json = json.loads(r.text)

            has_more_pages = response_json['data']['reportData']['reports']['has_more_pages']
            reports.extend(response_json['data']['reportData']['reports']['data'])
        except Exception:
            logger.exception(f'Failed to get reports data. Response: {r.text}.')
            raise
    # Before moving on, sort the reports by start date
    reports.sort(key=itemgetter('startTime'))
    logger.info(f'{len(reports)} reports found.')

    return reports


def get_abilities_cast_by_enemies_by_report_and_fight(token, report_id, fight_id, start_time, end_time):
    query_headers = {'Authorization': f'Bearer {token}'}
    logger.info(f'Querying FFLogs for abilities for report {report_id} and fight {fight_id}.')

    results = []
    while start_time:
        q = f"""query {{
            reportData {{
                report(code: "{report_id}") {{
                    events(
                            fightIDs: [{fight_id}],
                            startTime: {start_time},
                            endTime: {end_time},
                            dataType: Casts,
                            hostilityType: Enemies) {{
                        data
                        nextPageTimestamp
                    }}
                }}
            }}
        }}"""
        try:
            r = requests.get(constants.API_URL, headers=query_headers, json={'query': q})
            response_json = json.loads(r.text)

            start_time = response_json['data']['reportData']['report']['events']['nextPageTimestamp']
            results.extend(d for d in response_json['data']['reportData']['report']['events']['data'] if d['type'] == 'cast')
        except Exception:
            logger.exception(f'Failed to get ability cast data. Response: {r.text}.')
            raise
    return results


def get_zone_name(token, zone_id):
    query_headers = {'Authorization': f'Bearer {token}'}
    logger.info(f'Querying FFLogs for zone name.')

    q = f"""query {{
        worldData {{
            zone(id: {zone_id}) {{
                    name
            }}
        }}
    }}"""
    try:
        r = requests.get(constants.API_URL, headers=query_headers, json={'query': q})
        response_json = json.loads(r.text)

        return response_json['data']['worldData']['zone']['name']
    except Exception:
        logger.exception(f'Failed to get zone name. Response: {r.text}.')
        raise


def parse_pulls_from_reports(token, cache, reports, progress_indicators):
    logger.info('Parsing pulls from report data.')

    progress_indicators_by_index = {pi.index:pi for pi in progress_indicators}

    all_pulls = []
    for report in reports:
        report_id = report['code']

        # If the report data is cached, just use that data and move onto the next.
        cache_key = f'report_data/{report_id}'
        cached_report_data = cache.get(cache_key)
        if cached_report_data:
            logger.info(f'Using cached data of {len(cached_report_data)} pulls for report {report_id}.')

            # Rehydrate progress indicator cache incase of styling changes
            for fight in cached_report_data:
                fight.progress = progress_indicators_by_index[fight.progress.index]
            all_pulls.extend(cached_report_data)
            continue

        # Otherwise, load up data (and then cache it).
        pulls = []
        for fight in report['fights']:
            # Skip trash fights (encounterID=0)
            if fight['encounterID'] == 0:
                continue

            fight_id = fight['id']
            duration_in_seconds = (fight['endTime'] - fight['startTime']) / 1000  # times are stored in milliseconds
            pull = None
            for progress_indicator in sorted(progress_indicators, key=lambda pi: pi.index, reverse=True):
                if progress_indicator.matches(token, cache, report, fight):
                    pull = Pull(fight_id, report_id, progress_indicator, duration_in_seconds)
                    break

            # If we didn't generate a Pull from the abilities cast, that means that we probably died
            # before seeing anything (e.g. suicide after pulling too early,
            # died before seeing any spells cast, etc). Just discard these pulls.
            if not pull:
                continue

            pulls.append(pull)

        logger.info(f'No cached data for report {report_id}; writing {len(pulls)} pulls to cache.')
        cache.set(cache_key, pulls)
        cache.commit()
        all_pulls.extend(pulls)

    return all_pulls


def time_formatter(x, pos):
    try:
        minutes, seconds = int((x % 3600) // 60), int(x % 60)
        return '{:d}:{:02d}'.format(minutes, seconds)
    except:
        return 'n/a'


def setup_plot():
    plot.rcParams['font.family'] = 'Liberation Serif'
    # plot.rcParams['font.size'] = '16'

    figure, (axes, text_axes) = plot.subplots(1, 2, figsize=(10,5), gridspec_kw={'width_ratios': [10, 1]})
    figure.subplots_adjust(hspace=0, wspace=0.05)
    figure.autofmt_xdate()
    axes.set_xlabel('Pull Count')
    axes.set_ylabel('Pull Length')

    #axes.xaxis.set_minor_locator(MultipleLocator(base=10))
    axes.xaxis.set_major_locator(MultipleLocator(base=100))

    #axes.set_ylim(bottom=0, top=60*18)  # TODO: change as we prog lol
    axes.yaxis.set_minor_locator(MultipleLocator(base=30))

    axes.yaxis.set_major_formatter(FuncFormatter(time_formatter))
    axes.yaxis.set_major_locator(MultipleLocator(base=60))

    text_axes.axis('off')
    text_axes.set_xticklabels([])
    text_axes.set_yticklabels([])

    return figure, axes, text_axes


def plot_pull_data(title, pulls, progress_indicators, generate_gif=False):
    logger.info(f'Plotting data of {len(pulls)} pulls.')
    figure, axes, text_axes = setup_plot()

    # Create a text object that we'll keep updated throughout the plotting.
    text = text_axes.text(
        0,
        1,
        '',
        clip_on=False,
        size='large',
        linespacing=1.5,
        horizontalalignment='left',
        verticalalignment='top',
        multialignment='left',
    )

    if generate_gif:
        # We want a GIF at a specific FPS, but with the final frame being held for a few seconds.
        fps = 60
        last_frame_duration = 6.0
        frame_durations = [1.0 / fps] * len(pulls)
        frame_durations[-1] = last_frame_duration
        writer = imageio.get_writer('output/output.mp4', fps=60, quality=10)

    latest_kill_pull = 0
    longest_pull_time = 0.0
    best_kill_time = float('inf')
    latest_progress_index_seen = 0
    progress_occurrences = defaultdict(int)
    shading_colors = itertools.cycle(['black', 'white'])
    current_report_id = None
    current_shade_color = next(shading_colors)
    total_time = 0
    unique_reports = set()

    for pull_count, pull in enumerate(pulls, start=1):
        # Minor housekeeping to maintain "current report" shading and longest pull time
        if not current_report_id:
            current_report_id = pull.report_id
        elif pull.report_id != current_report_id:
            current_report_id = pull.report_id
            current_shade_color = next(shading_colors)

        if isinstance(pull.progress, VictoryIndicator):
            latest_kill_pull = pull_count
            best_kill_time = min(best_kill_time, pull.duration_in_seconds)

        longest_pull_time = max(longest_pull_time, pull.duration_in_seconds)
        latest_progress_index_seen = max(pull.progress.index, latest_progress_index_seen)
        progress_occurrences[pull.progress.index] = progress_occurrences[pull.progress.index] + 1
        total_time += pull.duration_in_seconds
        unique_reports.add(pull.report_id)

        axes.set_title(f'{title}: Pull #{pull_count}')
        default_style = {'marker': 'D', 'markersize': 4, 'alpha': 0.8}
        axes_style = default_style | pull.progress.style
        axes.plot(pull_count, pull.duration_in_seconds, **axes_style)
        axes.axvspan(max(pull_count - 1, 1), pull_count, color=current_shade_color, alpha=0.05, lw=0)

        # Unfortunately, we need to some disgusting basic math to get a clean HH:ss format
        hours, remainder = divmod(int(total_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        info_text = (
            f'Fastest kill: {time_formatter(best_kill_time, 0)}s\n'
            f'Session count: {len(unique_reports)}\n'
            f'Total time: {hours:02d}:{minutes:02d}:{seconds:02d}\n'
            f'Pulls since last kill: {pull_count - latest_kill_pull}\n'
        )
        text.set_text(info_text)

        # Generate the legend based on the progress we've seen
        label_fmt = '{} ({})'
        axes.legend(
            handles=[
                patches.Patch(label=f'{pi.label} ({progress_occurrences[pi.index]})', color=pi.style['color'])
                for pi in progress_indicators
                if pi.index <= latest_progress_index_seen
            ],
            loc='upper left',
        )

        if generate_gif:
            image_buffer = io.BytesIO()
            figure.savefig(image_buffer, format='png')
            image_buffer.seek(0)
            writer.append_data(imageio.imread(image_buffer))

        print(f'\r{100 * pull_count / len(pulls):.1f}% done processing.', end='')

    if generate_gif:
        writer.close()
    else:
        figure.savefig('output/output.png', format='png')


def main():
    config_filename = 'config.ini'
    config = ConfigParser()
    config.read(config_filename)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--generate-gif',
        action='store_true',
        help='Generates a GIF rather than a PNG file.',
        default=config.getboolean('main', 'GENERATE_GIF'),
    )
    args = parser.parse_args()

    cache = JsonFileCache('cache.json')

    # A list of progress indicating abilities.
    # Note: this is extremely dependent on having unique abilities cast per phase.
    # You can get these ability_ids from fflogs.com, or from abilities.json
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

    if not (token := config.get('main', 'TOKEN', fallback=None)):
        token = get_new_token(config.get('main', 'CLIENT_ID'), config.get('main', 'CLIENT_SECRET'))
        config['main']['TOKEN'] = token
        with open(config_filename, 'w') as f:
            config.write(f)

        logger.info('New token generated and config file updated.')

    logger.info('Token found.')

    user_id = config.getint('main', 'FFLOGS_USER_ID')
    zone_name = get_zone_name(token, constants.ZONE_ID)
    reports = get_reports(token, user_id, constants.ZONE_ID)
    all_pulls = parse_pulls_from_reports(token, cache, reports, progress_indicators)
    plot_pull_data(zone_name, all_pulls, progress_indicators, args.generate_gif)


if __name__ == '__main__':
    main()