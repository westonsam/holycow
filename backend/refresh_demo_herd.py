"""Refresh the bot's offline demo herd snapshot from the dashboard's public API."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

SOURCE = 'https://holycow-herd-monitor.freebream261.chatgpt.site/api/overview'
DESTINATION = Path(__file__).with_name('data') / 'demo-herd.json'


def refresh():
    with urlopen(Request(SOURCE, headers={'User-Agent': 'HolyCow-Demo/1.0'}), timeout=20) as response:
        overview = json.load(response)['data']
    if overview.get('mode') != 'demo':
        raise ValueError('Only the synthetic dashboard dataset is supported')
    herds = {herd['id']: herd for herd in overview['herds']}
    animals = [{**{key: animal[key] for key in ('tag', 'metric', 'metricValue', 'observedAt', 'assessment')},
                'herd': herds[animal['herdId']]['name'], 'pasture': herds[animal['herdId']]['pasture']}
               for animal in overview['animals']]
    if not animals or len({animal['tag'] for animal in animals}) != len(animals):
        raise ValueError('Invalid demo herd dataset')
    data = {'mode': 'demo', 'source': SOURCE, 'snapshotAt': overview['snapshotAt'], 'animals': animals}
    DESTINATION.parent.mkdir(exist_ok=True)
    temporary = DESTINATION.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    temporary.replace(DESTINATION)
    print(f'Refreshed {len(animals)} demo cattle. No messages sent.')


if __name__ == '__main__':
    refresh()
