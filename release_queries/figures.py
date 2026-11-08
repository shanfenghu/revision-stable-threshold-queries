"""Render neutral scientific displays from a verified replay and exact inputs.

Plotting is optional; the numerical replay and tests need only the standard library.
"""
from datetime import date, timedelta
from pathlib import Path
import json
from . import reproduce, construction, workloads


def availability(inputs, run):
    """Derive release offsets and the bounded missing-report example from records."""
    records = reproduce.verify_inputs(inputs)
    rows = []
    for record in records:
        if record['role'] == 'ili_evaluation':
            rows.extend(json.loads((inputs/record['path']).read_text())['epidata'])
    dated = [v for v in rows if v.get('release_date')]
    counts = {}
    for value in dated:
        offset = (date.fromisoformat(value['release_date'])-workloads.epiweek_end(value['issue'])).days
        counts[str(offset)] = counts.get(str(offset), 0)+1
    ledger = reproduce.read_json(run/'ledgers.json')['ili_evaluation']
    if counts != ledger['release_offset_days_counts']:
        raise ValueError('Plot source counts differ from the verified ledger')
    example = sorted((v for v in dated if v['epiweek'] == 201339 and v.get('num_ili') is not None),
                     key=lambda v: (v['release_date'], v['issue']))
    if not example:
        raise ValueError('No retained dated example; do not substitute another window')
    first = example[0]
    return {'offset_counts': counts, 'reference': 201339,
            'reference_date': workloads.epiweek_end(201339).isoformat(),
            'first_returned_lag': first['lag'], 'first_returned_count': first['num_ili'],
            'first_returned_date': first['release_date'],
            'returned_dates': [v['release_date'] for v in example]}


def run(inputs, run_directory, output):
    """Create three vector PDFs and the exact plotted numbers in a new directory."""
    inputs, run_directory, output = Path(inputs), Path(run_directory), Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('Figure output exists; choose a new directory')
    summary = reproduce.read_json(run_directory/'audits/summary.json')
    reproduce.compare(summary, reproduce.read_json(reproduce.ROOT/'expected/audits.json'))
    source = availability(inputs, run_directory)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.lines import Line2D
    output.mkdir(parents=True)
    finite = construction.render_figure(output/'construction.pdf')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8.5, 'pdf.fonttype': 42})
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.25), gridspec_kw={'width_ratios': [1, 1.6]}, layout='constrained')
    counts = source['offset_counts']; days = sorted(map(int, counts))
    axes[0].bar([str(v) for v in days], [counts[str(v)] for v in days], color='#365f80')
    axes[0].set_xlabel('Days after nominal Saturday'); axes[0].set_ylabel('Retained source records')
    for index, day in enumerate(days):
        axes[0].text(index, counts[str(day)]+18, str(counts[str(day)]), ha='center', fontsize=8)
    axes[0].set_ylim(0, max(counts.values())*1.18)
    ax = axes[1]; start = date.fromisoformat(source['reference_date'])
    first = date.fromisoformat(source['first_returned_date'])
    dates = [date.fromisoformat(v) for v in source['returned_dates']]; end = max(dates)+timedelta(days=3)
    ax.axvspan(start, first, color='#e8ecef'); ax.hlines(.5, start, end, color='#718896')
    for day in dates:
        ax.plot(day, .5, 'o', color='#b7602c', markersize=5)
    ax.annotate('First returned dated count: '+format(source['first_returned_count'], ',.0f'),
                xy=(first, .5), xytext=(date(2013, 10, 6), .86), arrowprops={'arrowstyle': '->'}, fontsize=8)
    ax.text(date(2013, 11, 10), .26, 'No returned dated count\nat lags 0-'+str(source['first_returned_lag']-1), ha='center', fontsize=8.5)
    ax.set_xlim(start, end); ax.set_ylim(.1, 1); ax.set_yticks([])
    ax.set_xticks([start, date(2013, 11, 1), first, max(dates)])
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b')); ax.tick_params(axis='x', labelsize=8)
    ax.set_title('Reference week 2013w39', fontsize=9)
    fig.savefig(output/'availability.pdf', metadata={'Title': 'Recorded availability', 'Author': '', 'CreationDate': None, 'ModDate': None}); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.35), sharey=True, layout='constrained')
    styles = [('primary', '#365f80', 'o', '-', -.13), ('lower_quartile_floor', '#b7602c', '^', '--', .13)]
    plotted = []
    for ax, domain, title in zip(axes, ['ili', 'gdp'], ['ILI', 'Real output']):
        windows = list(summary[domain]['primary']['windows'])
        for policy, color, marker, line, offset in styles:
            for index, window in enumerate(windows):
                value = summary[domain][policy]['windows'][window]
                if value['outcomes']['wrong_reuses'] != [0, 0]:
                    raise ValueError('This display requires reporting nonzero wrong reuse explicitly')
                low, high = value['outcomes']['reused']; total = value['answers']; x = index+offset
                reference = value['references']['continuous_revision']['reused']
                ax.plot([x, x], [100*low/total, 100*high/total], color=color, ls=line, lw=2)
                ax.scatter([x, x], [100*low/total, 100*high/total], color=color, marker=marker, s=15, zorder=4)
                ax.scatter([x+.045], [100*reference/total], marker='s', s=28, facecolor='white', edgecolor=color, lw=1.3, zorder=5)
                plotted.append({'domain': domain, 'policy': policy, 'window': window, 'denominator': total,
                                'minimum': low, 'maximum': high, 'continuous_revision': reference})
        ax.set_xticks(range(len(windows)), [v.capitalize()+'\n'+str(summary[domain]['primary']['windows'][v]['answers'])+' answers' for v in windows])
        ax.set_xlim(-.45, len(windows)-.55); ax.set_ylim(0, 100); ax.set_yticks([0, 25, 50, 75, 100]); ax.set_title(title, fontsize=9)
        ax.spines[['top', 'right']].set_visible(False); ax.grid(axis='y', alpha=.15); ax.set_axisbelow(True); ax.tick_params(axis='x', labelsize=8)
    axes[0].set_ylabel('Answers retained (%)')
    handles = [Line2D([0], [0], color=c, marker=m, ls=l, label=label) for (_, c, m, l, _), label in zip(styles, ['Median floor (primary)', 'Lower-quartile floor'])]
    handles.append(Line2D([0], [0], color='#555555', marker='s', markerfacecolor='white', ls='none', label='Continuous revision fit'))
    fig.legend(handles=handles, loc='outside upper center', ncol=3, frameon=False, fontsize=7.5)
    fig.savefig(output/'sensitivity.pdf', metadata={'Title': 'Normalisation sensitivity', 'Author': '', 'CreationDate': None, 'ModDate': None}); plt.close(fig)
    (output/'values.json').write_text(json.dumps({'construction': finite, 'availability': source, 'sensitivity': plotted}, indent=2)+'\n')
    return {'vector_figures': 3, 'plotted_policy_window_cases': len(plotted)}
