import csv
import os
import re
import inspect
from collections import Counter, defaultdict
from functools import wraps
from IPython.display import Markdown, display
from contextlib import contextmanager
from pprint import pprint

import matplotlib
from matplotlib import pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

import seaborn as sns
import pandas as pd
import dask.dataframe as dd


from dask.dataframe.core import Series as DaskSeries
from dask.array.core import Array as DaskArray
from dask.array import histogram as _dask_histogram

import sys
if sys.version_info < (3, 5):
    from pathlib2 import Path
else:
    from pathlib import Path

from collections import namedtuple

Distribution = namedtuple("Distribution", "min q1 median q3 max")




def tex_escape(text):
    """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX
    """
    conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
    }
    regex = re.compile('|'.join(re.escape(key) for key in sorted(conv.keys(), key = lambda item: - len(item))))
    return regex.sub(lambda match: conv[match.group()], text)


def relative_var(key, part, total, t1="{0:,}", t2="{0:.2%}"):
    relative_text = var(key, part / total, t2)
    part_text = var(key + "_total", part, t1)
    return "{} ({})".format(part_text, relative_text)


def var(key, value, template="{}"):
    result = template.format(value)
    latex_result = tex_escape(result)
    data = {}
    if os.path.exists("variables.dat"):
        with open("variables.dat", "r") as fil:
            for line in fil:
                line = line.strip()
                if line:
                    k, v = line.split(" = ")
                    data[k] = v
    data[key] = latex_result
    with open("variables.dat", "w") as fil:
        fil.writelines(
            "{} = {}\n".format(k, v)
            for k, v in data.items()
        )
    return result
            
        

def fetchgenerator(cursor, arraysize=1000):
    'An iterator that uses fetchmany to keep memory usage down'
    while True:
        results = cursor.fetchmany(arraysize)
        if not results:
            break
        yield from results
        
        
def dask_from_query(session, query, file):
    q = session.execute(query)
    with open(file, 'w') as outfile:
        outcsv = csv.writer(outfile)
        outcsv.writerow(x[0] for x in q.cursor.description)
        outcsv.writerows(fetchgenerator(q.cursor))
    return dd.read_csv(file)


def display_counts(
    counts, width=20, show_values=False, plot=True, template="{0:,g}", template2="{0:,g}", cut=None, logy=True
):
    counts = counts.compute() if isinstance(counts, DaskSeries) else counts
    if cut:
        counts = counts[cut]
    if isinstance(counts, pd.Series):
        counts = counts.to_frame()
    ax = counts.plot.bar(logy=logy)
    ax.get_yaxis().set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, p: template2.format(x)))
    if show_values:
        for p in ax.patches:
            text = template.format(int(p.get_height()))
            ax.annotate(text, (p.get_x() + 0.25, p.get_height() + 1.035), ha="center")
    fig = ax.get_figure()
    fig.set_size_inches(width, min(7, 0.375 * len(str(counts).split('\n'))), forward=True)
    if plot:
        plt.show()
        display(counts)
    else:
        return fig, counts



def violinplot(column, tick, lim):
    ax = sns.violinplot(x=column)
    fig = ax.get_figure()
    fig.set_size_inches(30, 5)
    plt.xlim(lim)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(tick))

    return Distribution(column.min(), column.quantile(0.25), column.median(), column.quantile(0.75), column.max())


def histogram(column, bins, tick, lim, ax=None):
    histfn = _dask_histogram if isinstance(column, DaskArray) else np.histogram
    hist, bins = histfn(column, bins=bins, range=lim)
    x = 0.5 * (bins[1:] + bins[:-1])
    width = np.diff(bins)
    ax = ax or plt.gca()
    fig = ax.get_figure()
    fig.set_size_inches(30, 5)
    ax.xaxis.set_major_locator(ticker.MultipleLocator(tick))
    ax.bar(x, hist, width);

dask_histogram = histogram

def numpy_distribution(column):
    return Distribution(
        column.min(),
        np.percentile(column, 25),
        np.median(column),
        np.percentile(column, 75),
        column.max()
    )


def counter_hist(counter, label="key", **kwargs):
    common = counter.most_common()
    arr = pd.DataFrame([c for n, c in common], index=[n for n, c in common], columns=[label])
    display_counts(arr, **kwargs)


def count(dataframe, *attrs):
    counter = Counter()
    for attr in attrs:
        counter[attr] = len(dataframe[dataframe[attr] != 0])
    return counter


def getitem(container, index, default=None):
    try:
        return container[index]
    except IndexError:
        return default


def describe_processed(series, statuses, show_undefined=False):
    result = Counter()
    for key, value in series.iteritems():

        if key < 0:
            print("Skipping: {}: {}".format(key, value))
            continue
        bits = [pos for pos, value in enumerate(bin(key)[2:][::-1]) if int(value)]
        if not bits:
            stat = statuses.get(0, "<undefined>")
            if stat == "<undefined>":
                print("Undefined: {}: {}".format(0, value))
            result[stat] += value
        else:
            for bit in bits:
                stat = statuses.get(2 ** bit, "<undefined>")
                if stat == "<undefined>":
                    print("Undefined: {}: {}".format(2 ** bit, value))
                result[stat] += value
    return pd.Series(result)


def distribution_with_boxplot(column, first, last, step, ylabel, xlabel, draw_values=True, bins=None, template_x="{:g}"):
    bins = bins if bins else last - first
    computed = column.compute() if isinstance(column, DaskSeries) else column
    distribution = numpy_distribution(computed)

    fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharex=True, gridspec_kw = {'height_ratios':[3, 1]})
    dask_histogram(column.values, bins, step, (first, last), ax=ax1)
    ax1.xaxis.tick_bottom()
    ax1.set_ylabel(ylabel)
    ax1.get_yaxis().set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, p: "{0:,g}".format(x)))

    bp = ax2.boxplot(computed, showfliers=False, vert=False, widths=[.5])
    ax2.yaxis.set_ticks_position('none')
    ax2.set_yticklabels([""])
    ax2.set_xlabel(xlabel)

    if draw_values:
        draw = defaultdict(list)
        for key, value in zip(distribution._fields, distribution):
            draw[float(value)].append(key)
        draw[bp['caps'][0].get_xdata()[0]].append("Q1 - 1.5*IQR")
        draw[bp['caps'][1].get_xdata()[0]].append("Q3 + 1.5*IQR")
        draw_list = []
        position = 0.6
        for value, keys in draw.items():
            if first <= value <= last:
                text = template_x.format(value)
                ax2.annotate(text, (value, position), ha="center")
                position = 0.6 if position > 1.0 else 1.3
            else:
                draw_list.append("{0}: {1}".format(", ".join(keys), template_x.format(value)))

        ax2.annotate("\n".join(draw_list), (last, 1), ha="right")

    plt.tight_layout()
    plt.subplots_adjust(hspace=0)
    return distribution


def boxplot_distribution(column, first, last, step, ylabel, xlabel, draw_values=True, show_list=False, bins=None, template_x="{:g}"):
    bins = bins if bins else last - first
    computed = column.compute() if isinstance(column, DaskSeries) else column
    distribution = numpy_distribution(computed)

    fig, ax2 = plt.subplots(nrows=1, ncols=1)

    bp = ax2.boxplot(computed, showfliers=False, vert=False, widths=[.5])
    ax2.yaxis.set_ticks_position('none')
    ax2.set_yticklabels([""])
    #ax2.set_xlabel(xlabel)
    #

    if draw_values:
        draw = defaultdict(list)
        for key, value in zip(distribution._fields, distribution):
            draw[float(value)].append(key)
        draw[bp['caps'][0].get_xdata()[0]].append("Q1 - 1.5*IQR")
        draw[bp['caps'][1].get_xdata()[0]].append("Q3 + 1.5*IQR")
        draw_list = []
        position = 0.6
        for value, keys in draw.items():
            if first <= value <= last:
                text = template_x.format(value)
                ax2.annotate(text, (value, position), ha="center")
                position = 0.6 if position > 1.0 else 1.3
            else:
                draw_list.append("{0}: {1}".format(", ".join(keys), template_x.format(value)))
        if show_list:
            ax2.set_xlim([first - step, last + step])
            ax2.annotate("\n".join(draw_list), (last, 1), ha="right")
    ax2.axis("off")
    plt.tight_layout()
    plt.subplots_adjust(hspace=0)
    return distribution

@contextmanager
def savefig(name, width=8, height=6):
    plt.rc('axes', titlesize=16) 
    plt.rc('axes', labelsize=16) 
    plt.rc('font', size=14)
    yield
    fig = plt.gcf()
    fig.set_size_inches(width, height)
    fig.savefig("outputs/{}.svg".format(name), bbox_inches='tight')
    fig.savefig("outputs/{}.pdf".format(name), bbox_inches='tight')
    fig.savefig("outputs/{}.png".format(name), bbox_inches='tight')


@contextmanager
def cell_distribution(filename, width, height, select, bins, cell_type_bins_arrays, colors=None, relative=True):
    bar_l = [i for i in range(bins + 1)]
    if relative:
        total = sum((cell_type_bins_arrays[key] for key in select),  np.zeros(bins + 1))
    with savefig(filename, width, height):
        bottom = np.zeros(bins + 1)
        ax = plt.gca()
        for key in select:
            column = cell_type_bins_arrays[key]
            if relative:
                column = column / total * 100
            kwargs = {}
            if colors and key in colors:
                kwargs["color"] = colors[key]
            bar = ax.bar(bar_l, column, bottom=bottom, label=key, alpha=0.9, width=1, **kwargs)
            bottom += column
        fig = ax.get_figure()
        fig.set_size_inches(width, height)
        ax.set_yticklabels([])
        ax.set_xticks([0, bins / 2, bins])
        ax.set_xlim(0, bins)
        plt.xticks(fontsize=14)
        ax.set_xticklabels(["Beginning", "Middle", "End"])
        ax.set_ylabel("% of Cells" if relative else "# of Cells", fontsize=16)
        yield ax
        ax.xaxis.set_ticks_position('none') 
        ax.yaxis.set_ticks_position('none') 
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_visible(False)
        ax.spines['left'].set_visible(False)

def calculate_all(config, args, function, result="Default", save_to=None, level=3):
    ip = get_ipython()
    ret = None
    for name, prefix in config.items():
        if level is not None:
            display(Markdown("#" * level + " " + name))
        value = function(*[ip.ns_table["user_global"][prefix + arg] for arg in args], prefix=prefix)
        if name == result:
            ret = value
        if save_to is not None:
            ip.ns_table["user_global"][prefix + save_to] = value
        elif value is not None:
            print(value)
    return ret

def calculate_auto(config, save_to=None, result=None, level=3):
    def dec(f):
        args = [
            x.name for x in inspect.signature(f).parameters.values()
             if x.name != 'prefix'
        ]
        return calculate_all(config, args, f, save_to=save_to, result=result, level=level)
    return dec

def close_fig(f):
    @wraps(f)
    def func(*args, **kwargs):
        res = f(*args, **kwargs)
        fig = plt.gcf()
        display(fig)
        plt.close(fig)
        return res
    return func

def print_result(f):
    @wraps(f)
    def func(*args, **kwargs):
        res = f(*args, **kwargs)
        pprint(res)
        return res
    return func
