#!/usr/bin/env python
#
# Copyright (C) 2003 Gre7g Luterman <gre7g@wolfhome.com>
#
# This file is part of TMDA.
#
# TMDA is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.  A copy of this license should
# be included in the file COPYING.
#
# TMDA is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with TMDA; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

"Local config file editor for tmda-cgi."

import os
import pickle
import re
import CgiUtil
import Template
from TMDA import Defaults
from TMDA import FilterParser

def Show():
  "Edit any plaintext list file."

  # Load the display template
  T = Template.Template("editlist.html")
  NoneList = T["NoneList"]

  # Find pre-calculated buttons
  Filename = os.path.join \
  (
    PVars.ThemesDir, PVars[("General", "Theme")], "subtopics.p"
  )
  F = open(Filename)
  SysButtons = pickle.load(F)
  F.close()

  # Load filters, find files used
  Buttons = {}
  for Filters in [Defaults.FILTER_INCOMING, Defaults.FILTER_OUTGOING]:
    Parser = FilterParser.FilterParser()
    Parser.read(CgiUtil.ExpandUser(Filters))
    for Test in Parser.filterlist:
      if Test[0] in ["from-file", "to-file", "body-file", "headers-file"]:
        Filename = os.path.split(Test[2])[1].lower()
        if SysButtons.has_key(Filename):
          Buttons[CgiUtil.ExpandUser(Test[2])] = \
            (Filename, SysButtons[Filename])
        else:
          Buttons[CgiUtil.ExpandUser(Test[2])] = \
            (Filename, SysButtons["other"])
  Files = Buttons.keys()

  if len(Files):
    # Which filter are we editing?
    if Form["cmd"].value == "editlist":
      EditFile = Files[0]
    else:
      EditFile = Files[int(Form["cmd"].value[8:])]

    # Get file
    T["FilePath"] = EditFile
    try:
      F = open(EditFile)
      T["FileContents"] = List = F.read()
      F.close()
    except IOError:
      T["FileContents"] = ""

  else:
    # The user has no text-based lists defined in their filters.
    T["NoLists"]
    NoneList.Add()

  # Generate button HTML
  HTML = ""
  for FileNum in range(len(Files)):
    File = Files[FileNum]
    if File == EditFile:
      HTML += '<tr><td><img src="%s/' % Template.Template.Dict["ThemeDir"]
      HTML += """%(hfn)s" width="%(width)d" height="%(height)d" alt=""" % \
        Buttons[File][1]
      HTML += '"%s"></td></tr>\n' % Buttons[File][0]
      T["ListNum"] = FileNum
    else:
      HTML += '<tr><td><a href="%s?cmd=editlist%d&SID=%s"><img src="%s/' % \
        (os.environ["SCRIPT_NAME"], FileNum, PVars.SID,
        Template.Template.Dict["ThemeDir"])
      HTML += """%(fn)s" border="0" width="%(width)d"
height="%(height)d" alt=""" % Buttons[File][1]
      HTML += '"%s"></td></tr>\n' % Buttons[File][0]
  T["Lists"] = HTML

  # Any subcommand?
  if Form.has_key("subcmd"):
    if Form["subcmd"].value == "sort":
      List = List.split("\n")
      List.sort()
      List = "\n".join(List)
    else:
      if Form.has_key("list"):
        List = Form["list"].value
      else:
        List = ""

    # Make sure the list is properly formatted
    List = re.sub("\r\n", "\n", List)
    List = re.sub("\n*$", "", List)
    List += "\n"

    try:
      F = open(EditFile, "w")
      F.write(List)
      F.close()
      T["FileContents"] = List
    except IOError, ErrStr:
      CgiUtil.TermError("Unable to save filter list.",
      "Insufficient privileges", "save list", "%s<br>%s" % (ErrStr,
      CgiUtil.FileDetails("Filter list", EditFile)),
      "Change file permissions on <tt>%s</tt>" % EditFile)

  # Display template
  print T