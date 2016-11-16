#!/usr/bin/env python3
"""Bot Commands related to or interactin with the scp-wiki."""

###############################################################################
# Module Imports
###############################################################################

import arrow
import random as rand
import functools
import re
import jinja2

from . import core, ext, parser, lex, stats, tools

###############################################################################
# Internal Methods
###############################################################################


def show_page(page, rating=True):
    attribution = page.build_attribution_string(
        templates=lex.show_page.templates._raw,
        group_templates=lex.show_page.group_templates._raw)
    out = lex.show_page.summary if rating else lex.show_page.nr_summary
    if page.name == 'scp-1848':
        r = rand.Random(int(arrow.now().format('YYYYMMDDHH')))
        rating = r.randrange(-160, -140)
    else:
        rating = page.rating
    return out(page=page, rating=rating, attribution=attribution)


def guess_author(func):
    """
    Decorator for guessing the author based on partial input.

    If no input is given, attempts to use the name of the user who
    issued the command as the name of the author.
    """
    @functools.wraps(func)
    def inner(inp, *args, **kwargs):
        text = (inp.text or inp.user).lower()
        authors = {i for p in core.pages for i in p.metadata}
        authors = sorted(i for i in authors if text in i.lower())

        if not authors:
            return lex.not_found.author
        elif len(authors) == 1:
            return func(inp, *args, author=authors[0], **kwargs)
        else:
            tools.save_results(inp, authors, lambda x: func(inp, x))
            return tools.choose_input(authors)

    return inner


###############################################################################
# Find And Lookup Functions
###############################################################################


def show_search_results(inp, results):
    """Process page search results."""
    if not results:
        return lex.not_found.page
    elif len(results) == 1:
        return show_page(results[0])
    else:
        tools.save_results(inp, results, show_page)
        return lex.search.default(results=results, count=len(results))


def show_search_summary(inp, results):
    if not results:
        return lex.not_found.page
    pages = ext.PageView(results).sorted('created')
    return lex.summary.search(
        count=pages.count,
        authors=len(pages.authors),
        rating=pages.rating,
        average=pages.average,
        first=arrow.get(pages[0].created).humanize(),
        last=arrow.get(pages[-1].created).humanize(),
        top_title=pages.sorted('rating')[-1].title,
        top_rating=pages.sorted('rating')[-1].rating)


def find_pages(
        pages, *, title, exclude, strict,
        tags, author, rating, created, fullname):
    tags = tags or ''
    for t in ['fragment', 'admin', 'template', '_sys']:
        if t not in tags:
            tags += ' -' + t
    pages = pages.tags(tags)
    if rating:
        pages = pages.with_rating(rating)
    if created:
        pages = pages.created(created)

    if author:
        pages = [
            p for p in pages if any(author in a.lower() for a in p.metadata)]
    if fullname:
        return [p for p in pages if p.name == fullname]

    results = []
    for p in pages:
        words = p.title.lower().split()
        words = {''.join(filter(str.isalnum, w)) for w in words}

        if exclude and words & set(exclude):
            continue
        if strict and not words >= set(strict):
            continue
        if title and not all(i in p.title.lower() for i in title):
            continue

        results.append(p)

    return results


def _page_search_base(inp, pages, *, summary, **kwargs):
    if not inp.text:
        return lex.input.incorrect
    func = show_search_summary if summary else show_search_results
    return func(inp, find_pages(pages, **kwargs))


@core.command
@core.alias('s')
@parser.search
def search(inp, **kwargs):
    """Find scp-wiki pages."""
    return _page_search_base(inp, core.pages, **kwargs)


@core.command
@parser.search
def tale(inp, **kwargs):
    """Find scp-wiki tales."""
    return _page_search_base(inp, core.pages.tags('tale'), **kwargs)


@core.command
@core.alias('wl')
@parser.search
def wandererslibrary(inp, **kwargs):
    """Find Wanderers' Library pages."""
    return _page_search_base(inp, core.wlpages, **kwargs)


@core.command
def tags(inp):
    """Find pages with the given tags."""
    return show_search_results(inp, core.pages.tags(inp.text))


@core.rule(r'(?i).*http[s]?://www\.scp-wiki\.net/([^/\s]+)(?:\s|$)')
@core.rule(r'(?i)^(scp-[^\s]+)\s*$')
@core.rule(r'(?i).*!(scp-[^\s]+)')
def name_lookup(inp):
    pages = [p for p in core.pages if p.name == inp.text.lower()]
    if not pages:
        pages = list(core.wiki.list_pages(
            body='title created_by created_at rating tags', category='*',
            name=inp.text.lower()))
    return show_search_results(inp, pages)


@core.command
@core.alias('au')
@guess_author
def author(inp, author):
    """Display author summary."""
    pages = core.pages.related(author)
    url = pages.tags('author')[0].url if pages.tags('author') else None
    url = ' ( {} )'.format(url) if url else ''
    pages = pages.articles
    if not pages:
        return lex.not_found.author
    template = '\x02{1.count}\x02 {0}'.format
    tags = ', '.join(template(*i) for i in pages.split_page_type().items())
    rels = ', '.join(template(*i) for i in pages.split_relation(author).items())
    last = sorted(pages, key=lambda x: x.created, reverse=True)[0]
    return lex.summary.author(
        name=author, url=url, pages=pages, rels=rels, tags=tags,
        primary=pages.primary(author), last=last)


@core.command
@core.alias('ad')
@guess_author
def authordetails(inp, author):
    """Generate detailed statistics about the author."""
    return stats.update_user(author)


###############################################################################
# Errors
###############################################################################


def errors_orphaned():
    urls = [p.url for p in core.pages]
    urls.extend([p.url for p in core.wiki.list_pages(
        name='scp-*', created_at='last 3 hours')])
    pages = [k for k in core.wiki.titles() if k not in urls]
    pages = [p for p in pages if re.search(r'/scp-[0-9]{3,4}$', p)]
    return map(core.wiki, pages)


def errors_untagged():
    return core.wiki.list_pages(tags='-')


def errors_untitled():
    pages = core.pages.tags('scp').pages
    pages.extend(core.wiki.list_pages(name='scp-*', created_at='last 3 hours'))
    pages = [p for p in pages if p.url not in core.wiki.titles()]
    pages = [p for p in pages if p.is_mainlist]
    pages = [p for p in pages if 'scp-1848' not in p.url]
    return pages


def errors_deleted():
    return core.wiki.list_pages(category='deleted')


def errors_vote():
    return core.wiki.list_pages(
        tags='-in-deletion -archived -author -in-rewrite',
        rating='<-10', created_at='older than 24 hours')


@core.require(channel=core.config.irc.sssc)
@core.command
@core.multiline
def errors(inp):
    """
    Dispay an error report.

    Staff-only command.
    """
    all_pages = []

    for name in ['untagged', 'untitled', 'deleted', 'vote', 'orphaned']:
        pages = list(eval('errors_' + name)())
        if not pages:
            continue
        all_pages.extend(pages)
        pages = [p.url.split('/')[-1] for p in pages]
        pages = map('\x02{}\x02'.format, sorted(pages))
        yield getattr(lex.errors, name)(pages=', '.join(pages))

    if not all_pages:
        yield lex.errors.none
    else:
        tools.save_results(inp, all_pages, show_page)
        yield lex.errors.done


@core.command
@core.require(channel=core.config.irc.sssc)
@core.cooldown(7200)
@core.multiline
def cleantitles(inp):
    """
    Remove orphaned scp titles from the series pages.

    Staff-only command.
    """
    yield lex.cleantitles.start

    pages = [
        'scp-series', 'scp-series-2', 'scp-series-3',
        'joke-scps', 'scp-ex', 'archived-scps']
    wiki = core.pyscp.wikidot.Wiki('scp-wiki')
    wiki.auth(core.config.wiki.name, core.config.wiki.password)
    orphaned = [p.url.split('/')[-1] for p in errors_orphaned()]

    def clean_line(line, purge):
        pattern = r'^\* \[\[\[([^\]]+)\]\]\] - .+$'
        parsed = re.match(pattern, line)
        if not parsed:
            return line
        name = parsed.group(1)
        if name.lower() not in orphaned:
            return line
        if not purge:
            return '* [[[{}]]] - [ACCESS DENIED]'.format(name)

    for page in map(wiki, pages):
        source = page.source.split('\n')
        purge = 'scp-series' not in page.url
        source = [clean_line(i, purge) for i in source]
        source = [i for i in source if i is not None]
        source = '\n'.join(source)
        if source != page.source:
            page.edit(source, comment='clean titles')

    core.wiki.titles.cache_clear()
    yield lex.cleantitles.end


###############################################################################
# Misc
###############################################################################


@core.command
@parser.random
def random(inp, **kwargs):
    """Get a random page."""
    pages = find_pages(core.pages, **kwargs) if inp.text else core.pages
    if pages:
        return show_page(rand.choice(pages))
    else:
        return lex.not_found.page


@core.command
@core.alias('lc')
@core.cooldown(120)
@core.multiline
def lastcreated(inp, cooldown={}, **kwargs):
    """Display most recently created pages."""
    kwargs = dict(
        body='title created_by created_at rating',
        order='created_at desc',
        rating='>=-15',
        limit=3)
    pages = core.wiki.list_pages(**kwargs)
    rating = inp.channel == core.config.irc.sssc
    return [show_page(p, rating=rating) for p in pages]


@core.command
@parser.unused
def unused(inp, *, random, last, count, prime, palindrome, divisible):
    """Get the first unused scp slot."""
    numbers = range(2, 3000)

    if prime:
        numbers = [i for i in numbers if all(i % k for k in range(2, i))]
    if palindrome:
        numbers = [
            i for i in numbers if str(i).zfill(3) == str(i).zfill(3)[::-1]]
    if divisible:
        numbers = [i for i in numbers if i % divisible == 0]

    slots = ['scp-{:03d}'.format(i) for i in numbers]
    used_slots = {p.name for p in core.pages.tags('scp')}
    unused_slots = [i for i in slots if i not in used_slots]

    if not unused_slots:
        return lex.not_found.unused

    if count:
        return lex.unused.count(count=len(unused_slots))

    if random:
        result = rand.choice(unused_slots)
    elif last:
        result = unused_slots[-1]
    else:
        result = unused_slots[0]

    return 'http://www.scp-wiki.net/' + result


@core.command
def staff(inp, staff={}):
    """Display a blurb for the given staff member."""
    if not inp.text:
        return 'http://www.scp-wiki.net/meet-the-staff'

    cats = {'Admin': 1, 'Mod': 2, 'Staff': 3}

    if not staff:
        for key in cats:
            staff[key] = {}

        soup = core.wiki('meet-the-staff')._soup
        for k, v in cats.items():
            for i in soup(class_='content-panel')[v]('p'):
                staff[k][i.strong.text.lower()] = i.text

    for cat in cats:
        for k, v in staff[cat].items():
            if inp.text.lower() in k:
                return '[{}] {}'.format(cat, v)

    return lex.not_found.staff
