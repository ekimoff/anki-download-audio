#!/usr/bin/env python
# -*- mode: python ; coding: utf-8 -*-
#
# Copyright © 2012 Roland Sieker, <ospalh@gmail.com>
# License: GNU GPL, version 3 or later; http://www.gnu.org/copyleft/gpl.html

import re
from aqt import mw
from anki.template import furigana
from anki.utils import stripHTML

"""
Extract field data to download.
"""


## Change these to mach the field names of your decks. Make sure to
## not use capital letters. We compare these to lower-case only
## versions of the field names. When these lists contain upper-case
## letters, no field will ever be matched and nothing will be
## downloaded.
expression_fields = ['expression', 'front', 'back']
"""Fields we get our Google TTS download text from."""

reading_keys = ['reading', 'kana', u'かな', u'仮名', 'hanzi', 'pinyin']
"""Fields we get our Japanese (or possibly Chinese) download text from."""

audio_field_keys = ['audio', 'sound']
"""Fields we put our downloaded sounds in."""


# Change this at your own risk.
field_name_re = '{{(?:[/^#]|[^:}]+:|)([^:}{]*%s[^:}{]*)}}'


def uniqify_list(seq):
    """Return a copy of the list with every element appearing only once."""
    # From http://www.peterbe.com/plog/uniqifiers-benchmark
    no_dupes = []
    [no_dupes.append(i) for i in seq if not no_dupes.count(i)]
    return no_dupes


def field_data(note, fname, readings):
    """
    Return a suitable source field name and the text in that field.

    Look for a suitable field to get the source text from and return it.
    If no suitable field is found, a KeyError is raised.

    There are four ways the source field is determined:
    * First we look for a reading field:
      * when fname is in one of the strings is audio_field_key,
        expression_fields is used as list of candidates
      * when the audio_field_key is only a substring of fname, that substring
        and a trailing or leading ' ' or '_' is removed and that used
        as the candidate.
    * readings is True:
      * when fname is in one of the strings is audio_field_key,
        reading_keys is used as list of candidates
      * when the audio_field_key is only a substring, that substring
        is replaced by the strings from reading_keys

    The first field that matches the candidate is used.  Comparisions
    are done with lowercase strings, the uppercase name is returned.

    Also returned is the text from the field, always as three strings
    now, just cleaned up and split into base (kanji) and ruby (furigana).
    """
    def return_data(idx, split_result):
        """
        Return a cleaned-up version of the field content.

        Get the text, remove html, and return the field name, the
        clean text, and what we got when we tried to split into kanji
        and kana, when different from the text.
        """
        text = note[field_names[idx]]
        # This is taken from aqt/browser.py.
        text = text.replace(u'<br>', u' ')
        text = text.replace(u'<br />', u' ')
        text = stripHTML(text)
        # Reformat so we have exactly one space between words.
        text = u' '.join(text.split())
        if not text:
            raise ValueError('Source field empty')
        if split_result:
            base = furigana.kanji(text)
            ruby = furigana.kana(text)
            text = u''
        else:
            base = u''
            ruby = u''
        return field_names[idx], fname, text, base, ruby

    t_name = fname.lower()
    field_names = [item[0] for item in note.items()]
    f_names = [fn.lower() for fn in field_names]
    # First, look if we have a
    for afk in audio_field_keys:
        if t_name == afk:
            if readings:
                sources_list = reading_keys
            else:
                sources_list = expression_fields
            for cnd in sources_list:
                for idx, lname in enumerate(f_names):
                    if cnd == lname:
                        return return_data(idx)
            # At this point: The target name is good, but we found no
            # source name.
            raise KeyError('No source name found (case 1)')
        # This point: target name is not exactly the field name
        if not afk in t_name:
            # And not a substring either
            continue
        # Here: the field name contains an audio or sound.
        # Mangle the name as described. For the readings case we get a
        # list. So do a list for the other case as well.
        if readings:
            sources_list = [t_name.replace(afk, rk)
                            for rk in reading_keys]
        else:
            # Here the tricky bit is to remove the right number of '_'
            # or ' ' characters, 0 or 1, but not 2. What we want is:
            # ExampleAudio -> Example
            # Example_Audio -> Example
            # Audio_Example -> Example
            # but
            # Another_Audio_Example -> Another_Example, not Another_Example
            # While a bit tricky, this is not THAT hard to do. (Not
            # lookbehind needed.)
            sources_list = [re.sub('[\s_]{0}|{0}[\s_]?'.format(re.escape(afk)),
                                   '', t_name, count=1)]
        for cnd in sources_list:
            for idx, lname in enumerate(f_names):
                if cnd == lname:
                    return return_data(idx)
        # We do have audio or sound as sub-string but did not find a
        # maching field.
        raise KeyError('No source field found. (case 2)')
    # No audio field at all.
    raise KeyError('No source field found. (case 3)')


def get_side_fields(card, note):
    """
    Get a list of field data for "visible" download fields.

    Check the visible side of the current card for fields that contain
    a string from audio_field_keys.  Then check the note for these
    fields and suitable data source fields.
    """
    if 'question' == mw.reviewer.state:
        template = card.template()[u'qfmt']
    else:
        template = card.template()[u'afmt']
    audio_field_name_list = []
    for afk in audio_field_keys:
        # Append all fields in the current template/side that contain
        # 'audio' or 'sound'
        audio_field_name_list += re.findall(field_name_re % (re.escape(afk), ),
                                            template, flags=re.IGNORECASE)
    audio_field_name_list = uniqify_list(audio_field_name_list)
    all_field_names = [item[0] for item in note.items()]
    # Filter out non-existing fields.
    audio_field_name_list = [fn for fn in audio_field_name_list
                             if fn in all_field_names]
    field_data_list = []
    for fname in audio_field_name_list:
        try:
            # This is changed now. Instead of saying if we want
            # reading or not, we first look for a reading field and
            # when we don't find one, look for a general source
            # field. Also, we always get three source data strings
            # now.
            field_data_list.append(
                field_data(note, fname, readings=True))
        except KeyError:
            # No reading field
            try:
                field_data_list.append(
                    field_data(note, fname, readings=False))
            except (KeyError, ValueError):
                # No or empty 'normal' field.
                pass
        except ValueError:
            # Found empty field
            pass
    return field_data_list


def get_note_fields(note):
    """
    Get a list of field data for download.

    Check all field names and return source and destination fields for
    downloading audio.
    """
    field_names = [item[0] for item in note.items()]
    field_data_list = []
    for afk in audio_field_keys:
        for fn in field_names:
            if afk in fn.lower():
                try:
                    # Here, too, first try reading, then try other
                    # fields.
                    field_data_list.append(
                        field_data(note, fn, readings=True))
                except KeyError:
                    # No readings field.
                    try:
                        # So look for 'normal' field.
                        field_data_list.append(
                            field_data(note, fn, readings=False))
                    except (KeyError, ValueError):
                        # No or empty 'normal' field
                        pass
                except ValueError:
                    # Empty readings field
                    pass
    return field_data_list
