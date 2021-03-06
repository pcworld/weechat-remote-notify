#!/usr/bin/env python
# -*- coding: utf-8 -*-
# ex:sw=4 ts=4:ai:
#
# Copyright (c) 2012 by Jan Christop Uhde <linux@obiwahn.org>
#   based on: pyrnotify by Krister Svanlund <krister.svanlund@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# Example usage when Weechat is running on a remote PC and you want
# want to use port 4321 for the connection.
#
#   On the "client" (where the notifications will end up), host is
#   the remote host where weechat is running:
#       python2 location/of/pyrnotify.py 4321 & ssh -R 4321:localhost:4321 username@host
#   Important to remember is that you should probably setup the
#   connection with public key encryption and use something like
#   autossh to do this in the background.
#
#   In weechat:
#   /python load remote-notify.py
#   and set the port
#   /set plugins.var.python.remote-notify.port 4321
#
# It is also possible to set which host pyrnotify shall connect to,
# this is not recommended. Using a ssh port-forward is much safer
# and doesn't require any ports but ssh to be open.
#
# Alternatively, you can create a new SSH connection (or run any other
# arbitrary command) for every notification. This has the advantage of
# not having to open up a TCP port (which can typically be accessed by
# all users on the machine running weechat).
#
#   In weechat:
#   /python load remote-notify.py
#   and set the command to run:
#   /set plugins.var.python.remote-notify.notify_command ssh client.example.org /path/to/weechat-remote-notify.py -
#
#   The /path/to/weechat-remote-notify.py is the path on the "client"
#   machine. Note the "-" argument, which indicates that a single
#   notification should be read from stdin, instead of the default
#   behaviour of spawning a TCP server.

try:
    import weechat as w
    in_weechat = True
except ImportError as e:
    in_weechat = False

import os, sys, re
import socket
import subprocess
import shlex

from pprint import pprint as pprint

SCRIPT_NAME    = "remote-notify"
SCRIPT_AUTHOR  = "Jan Christoph Uhde <linux@obiwahn.org>"
SCRIPT_VERSION = "0.1"
SCRIPT_LICENSE = "GPL3"
SCRIPT_DESC    = "Send remote notifications over sockets"

def run_notify(mtype,urgency,icon,time,nick,chan,message):
    data  = str(mtype) + "\n"
    data += str(urgency) + "\n"
    data += str(icon) + "\n"
    data += str(time) + "\n"    #time to display TODO
    data += str(nick) + "\n"
    data += str(chan) + "\n"
    data += str(message)

    transport = w.config_get_plugin('transport')
    command = w.config_get_plugin('notify_command'),
    host = w.config_get_plugin('host')

    try:
        if command:
            p = subprocess.Popen(command, shell=True,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
            (output, _) = p.communicate(data)
            if p.returncode != 0:
                raise Exception("Notify command failed with return code " + str(p.returncode) + "\r\n" + output)
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((host, int(w.config_get_plugin('port'))))
            s.send(str(data))
            s.close()
    except Exception as e:
        if w.config_string_to_boolean(w.config_get_plugin("display_errors")):
            w.prnt("", "Could not send notification: %s" % str(e))
            w.prnt("", "To hide errors, run: /set plugins.var.python.remote-notify.display_errors off")

def on_msg(*a):
    if len(a) == 8:
        data, buffer, timestamp, tags, displayed, highlight, sender, message = a
        #return when sender is weechat.look.prefix_network
        option = w.config_get("weechat.look.prefix_network")
        if sender == w.config_string(option):
            return w.WEECHAT_RC_OK
        if data == "private" or highlight == "1":

            #set buffer
            buffer = "me" if data == "private" else w.buffer_get_string(buffer, "short_name")

            #set time - displays message forever on highlight
            if highlight == "1" and data == "private":
                mtype = "private_highlight"
                icon = w.config_get_plugin('pm-icon')
                time = w.config_get_plugin('display_time_private_highlight')
            elif highlight == "1":
                mtype = "highlight"
                icon = w.config_get_plugin('icon')
                time = w.config_get_plugin('display_time_highlight')
            else:
                mtype = "private"
                icon = w.config_get_plugin('pm-icon')
                time = w.config_get_plugin('display_time_default')

            urgency = w.config_get_plugin('urgency_default')

            #sent
            run_notify(mtype, urgency, icon, time, sender, buffer, message)
            #w.prnt("", str(a))
    return w.WEECHAT_RC_OK

def weechat_script():
    settings = {'notify_command' : "",
                'host' : "localhost",
                'port' : "4321",
                'icon' : "utilities-terminal",
                'pm-icon' : "emblem-favorite",
                'urgency_default' : 'normal',
                'display_time_default' : '10000',
                'display_time_highlight' : '30000',
                'display_time_private_highlight' : '0',
                'display_errors' : 'on'}

    if w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE, SCRIPT_DESC, "", ""):
        for (kw, v) in settings.items():
            if not w.config_get_plugin(kw):
                w.config_set_plugin(kw, v)
        w.hook_print("", "notify_message",   "", 1, "on_msg", "")
        w.hook_print("", "notify_private",   "", 1, "on_msg", "private")
        w.hook_print("", "notify_highlight", "", 1, "on_msg", "") # Not sure if this is needed



######################################
## This is where the client starts, except for the global if-check nothing below this line is
## supposed to be executed in weechat, instead it runs when the script is executed from
## commandline.

def accept_connections(s):
    while True:
        conn, addr = s.accept()
        try:
            data = ""
            d = conn.recv(1024)
            while d:
                data += d
                d = conn.recv(1024)
        finally:
            conn.close()
        if data:
            handle_data(data)

def handle_data(data):
    try:
        mtype, urgency, icon, time, nick, chan, body = data.split('\n')
        title = nick + " to " + chan
        args=["notify-send", "-u", urgency, "-t", time, "-c", "IRC", "-i", icon, title, body ]
        #pprint(args)
        subprocess.Popen(args)

        sound="/usr/share/sounds/purple/receive.wav"
        subprocess.call(["play", "-V0", "-q", sound])
    except ValueError as e:
        print e
    except OSError as e:
        print e

def weechat_client(argv):
    if len(argv) > 1 and argv[1] == '-':
        handle_data(sys.stdin.read())
        return

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("localhost", int(argv[1] if len(argv) > 1 else 4321)))
    s.listen(5)
    try:
        accept_connections(s)
    except KeyboardInterrupt as e:
        print "Keyboard interrupt"
        print e
    finally:
        s.close()

if __name__ == '__main__':
    if in_weechat:
        weechat_script()
    else:
        weechat_client(sys.argv)
