#!/usr/bin/env python3

###############################################################################
# Module Imports
###############################################################################

import sopel
import jarvis

###############################################################################


@sopel.module.commands('google', 'g')
def google(bot, tr):
    g = bot.config.google
    bot.send(jarvis.websearch.google_search(g.apikey, g.cseid, tr.group(2)))


@sopel.module.commands('gis')
def gis(bot, tr):
    g = bot.config.google
    bot.send(
        jarvis.websearch.google_image_search(g.apikey, g.cseid, tr.group(2)))


@sopel.module.commands('youtube')
def youtube(bot, tr):
    g = bot.config.google
    bot.send(jarvis.websearch.youtube_search(g.apikey, tr.group(2)))


@sopel.module.rule(r'.*youtube\.com/watch\?v=([-_a-z0-9]+)')
@sopel.module.rule(r'.*youtu\.be/([-_a-z0-9]+)')
def youtube_lookup(bot, tr):
    g = bot.config.google
    bot.send(jarvis.websearch.youtube_video_info(g.apikey, tr.group(1)))


@sopel.module.commands('wikipedia')
def wikipedia(bot, tr):
    bot.send(jarvis.websearch.wikipedia_search(tr.group(2), tr.sender))


@sopel.module.commands('definition', 'define', 'dictionary')
def define(bot, tr):
    bot.send(jarvis.websearch.dictionary_search(tr.group(2), tr.sender))


@sopel.module.commands('urbandictionary')
def urbandictionary(bot, tr):
    bot.send(jarvis.websearch.urbandictionary_search(tr.group(2), tr.sender))