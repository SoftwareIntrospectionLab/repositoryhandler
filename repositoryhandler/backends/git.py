# git.py
#
# Copyright (C) 2007 Carlos Garcia Campos <carlosgc@gsyc.escet.urjc.es>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

import os
import re

from repositoryhandler.Command import Command, CommandError
from repositoryhandler.backends import Repository, RepositoryInvalidWorkingCopy, register_backend
from repositoryhandler.backends.watchers import *

def get_config (path, option = None):
    if os.path.isfile (path):
        path = os.path.dirname (path)

    cmd = ['git', 'config']

    if option is not None:
        cmd.extend (['--get', option])
    else:
        cmd.extend (['-l'])

    command = Command (cmd, path, env = {'PAGER' : ''})
    out = command.run_sync ()

    if option is not None:
        return out.strip ('\n\t ')

    retval = {}
    for line in out.splitlines ():
        if '=' not in line:
            continue
        key, value = line.split ('=', 1)
        retval[key.lower ().strip ()] = value.strip ('\n\t ')

    if retval == {}:
        return None

    return retval

def get_repository_from_path (path):
    if os.path.isfile (path):
        path = os.path.dirname (path)

    dir = path
    while dir and not os.path.isdir (os.path.join (dir, ".git")) and dir != "/":
        dir = os.path.dirname (dir)

    if not dir or dir == "/":
        raise RepositoryInvalidWorkingCopy ('"%s" does not appear to be a Git working copy' % path)
    
    try:
        uri = get_config (dir, 'remote.origin.url')
    except CommandError:
        uri = dir

    if uri is None or not uri:
        raise RepositoryInvalidWorkingCopy ('"%s" does not appear to be a Git working copy' % path)

    return 'git', uri
        
class GitRepository (Repository):
    '''Git Repository'''

    def __init__ (self, uri):
        Repository.__init__ (self, uri, 'git')

        self.git_version = None
    
    def _check_uri (self, uri):
        type, repo_uri = get_repository_from_path (uri)
        if not repo_uri.startswith (self.uri):
            raise RepositoryInvalidWorkingCopy ('"%s" does not appear to be a Git working copy '
                                                '(expected %s but got %s)' % (uri, self.uri, repo_uri))

    def _get_git_version (self):
        if self.git_version is not None:
            return self.git_version

        cmd = ['git', '--version']

        command = Command (cmd)
        out = command.run_sync ()

        version = out.replace ("git version ", "")
        self.git_version = tuple ([i for i in version.split ('.')])

        return self.git_version

    def _get_branches (self, path):
        cmd = ['git', 'branch']
        
        command = Command (cmd, path)
        out = command.run_sync ()

        patt = re.compile ("^\* (.*)$")
        
        i = 0
        current = 0
        retval = []
        for line in out.splitlines ():
            if line.startswith (self.uri):
                continue

            match = patt.match (line)
            if match:
                current = i
                retval.append (match.group (1).strip (' '))
            else:
                retval.append (line.strip (' '))
            i += 1

        return current, retval
    
    def _checkout_branch (self, path, branch):
        self._check_uri (path)

        current, branches = self._get_branches (path)

        if branch in branches:
            if branches.index (branch) == current:
                return

            cmd = ['git', 'checkout', branch]
        else:
            cmd = ['git', 'checkout', '-b', branch, 'origin/%s' % (branch)]
            
        command = Command (cmd, path)
        command.run ()

    def __get_root_dir (self, uri):
        if uri != self.uri:
            directory = os.path.dirname (uri)
            while directory and not os.path.isdir (os.path.join (directory, ".git")):
                directory = os.path.dirname (directory)
        else:
            directory = uri

#        if not git_dir.endswith((".git", ".git/")):
#            git_dir = git_dir + "/.git/"

#        os.putenv("GIT_DIR", git_dir)

        return directory or self.uri


    def checkout (self, module, rootdir, newdir = None, branch = None, rev = None):
        if newdir is not None:
            srcdir = os.path.join (rootdir, newdir)
        elif newdir == '.':
            srcdir = rootdir
        else:
            if module == '.':
                srcdir = os.path.join (rootdir, os.path.basename (self.uri.rstrip ('/')))
            else:
                srcdir = os.path.join (rootdir, module)
        if os.path.exists (srcdir):
            try:
                self.update (srcdir, rev)
                return
            except RepositoryInvalidWorkingCopy:
                # If srcdir is not a valid working copy,
                # continue with the checkout
                pass

        # module == '.' is a special case to download the whole repository
        if module == '.':
            uri = self.uri
        else:
            uri = os.path.join (self.uri, module)

        cmd = ['git', 'clone', uri]

        if newdir is not None:
            cmd.append (newdir)
        elif module == '.':
            cmd.append (os.path.basename (uri.rstrip ('/')))
        else:
            cmd.append (module)

        command = Command (cmd, rootdir)
        self._run_command (command, CHECKOUT)

        if branch is not None:
            self._checkout_branch (srcdir, branch)

    def update (self, uri, rev = None):
        self._check_uri (uri)

        branch = rev
        if branch is not None:
            self._checkout_branch (uri, branch)
        
        cmd = ['git', 'pull']

        if os.path.isfile (uri):
            directory = os.path.dirname (uri)
        else:
            directory = uri

        command = Command (cmd, directory)
        self._run_command (command, UPDATE)

    def cat (self, uri, rev = None):
        self._check_uri (uri)

        cmd = ['git', 'show']

        cwd = self.__get_root_dir (uri)
        target = uri[len (cwd):].strip ("/")

        if rev is not None:
            target = "%s:%s" % (rev, target)
        else:
            target = "HEAD:%s" % (target)

        cmd.append (target)
            
        command = Command (cmd, cwd, env = {'PAGER' : ''})
        self._run_command (command, CAT)
        
    def size (self, uri, rev = None):
        self._check_uri (uri)

        cmd = ['git', 'cat-file', '-s']

        cwd = self.__get_root_dir (uri)
        target = uri[len (cwd):].strip ("/")

        if rev is not None:
            target = "%s:%s" % (rev, target)
        else:
            target = "HEAD:%s" % (target)

        cmd.append (target)
        
        command = Command (cmd, cwd, env = {'PAGER' : ''})
        self._run_command (command, SIZE)
        
    def log (self, uri, rev = None, files = None, branch = None):
        self._check_uri (uri)

        if os.path.isfile (uri):
            cwd = os.path.dirname (uri)
            files = [os.path.basename (uri)]
        elif os.path.isdir (uri):
            cwd = uri
        else:
            cwd = os.getcwd ()

        cmd = ['git', 'log', '--topo-order', '--pretty=fuller', '--parents', '--name-status', '-M', '-C', '--cc']

        # Git < 1.6.4 -> --decorate
        # Git = 1.6.4 -> broken
        # Git > 1.6.4 -> --decorate=full
        try:
            major, minor, micro = self._get_git_version ()
        except ValueError:
            major, minor, micro, extra = self._get_git_version ()

        # Decorate adds branch specifications that we don't want the
        # parser to see
        if branch is None:
            if major <= 1 and minor < 6:
                cmd.append ('--decorate')
            elif major <= 1 and minor == 6 and micro <= 4:
                cmd.append ('--decorate')
            else:
                cmd.append ('--decorate=full')
        
        # --all overrides branch specifications
        if branch is None:
            cmd.append('--all')

        try:
            get_config (uri, 'remote.origin.url')
            
            location = "origin"
            
            # Remember that for Git, if you want to reference a
            # a remote branch, you'll need something like
            # 'origin/branch'. This isn't added automatically so
            # local branches can also be referenced.
            if branch is not None:
                location = branch
                
            cmd.append (location)
        except CommandError:
            pass

        if rev is not None:
            cmd.append (rev)

        if files is not None:
            for file in files:
                cmd.append (file)
        elif cwd != uri:
            cmd.append (uri)

        command = Command (cmd, cwd, env = {'PAGER' : ''})
        self._run_command (command, LOG)

    def rlog (self, module = None, rev = None, files = None):
        # Not supported by Git
        return

    def diff (self, uri, branch = None, revs = None, files = None):
        self._check_uri (uri)

        if os.path.isfile (uri):
            cwd = self.__get_root_dir (uri)
            files = [uri[len (cwd):].strip ("/")]
        elif os.path.isdir (uri):
            cwd = uri
        else:
            cwd = os.getcwd ()

        cmd = ['git', 'diff']

        if revs is not None:
            if len (revs) == 1:
                cmd.append (revs[0])
            elif len (revs) > 1:
                cmd.append ("%s..%s" % (revs[0], revs[1]))

        cmd.append ("--")

        if files is not None:
            cmd.extend (files)

        command = Command (cmd, cwd, env = {'PAGER' : ''})
        self._run_command (command, DIFF)

    def show (self, uri, rev = None):
        self._check_uri (uri)

        if os.path.isfile (uri):
            cwd = self.__get_root_dir (uri)
            target = uri[len (cwd):].strip ("/")
        elif os.path.isdir (uri):
            cwd = uri
            target = None
        else:
            cwd = os.getcwd ()
            target = None

        cmd = ['git', 'show', '--find-copies', '--pretty=format:']

        if rev is not None:
            cmd.append (rev)

        cmd.append ("--")

        if target is not None:
            cmd.append (target)

        command = Command (cmd, cwd, env = {'PAGER' : ''})
        self._run_command (command, DIFF)

    def blame (self, uri, rev = None, files = None, **kargs):
        self._check_uri (uri)

        cwd = self.__get_root_dir(uri)
        if uri.startswith(cwd) and len(uri) > len(cwd):
           files = [uri[len(cwd)+1:]]

        cmd = ['git', 'blame', '--root', '-l', '-t', '-f']

        if kargs.get('mc'):
            cmd.extend (['-M', '-C'])
        
        start = kargs.get('start')
        end = kargs.get('end')
        if start and end:
            cmd.extend(['-L',"%d,%d"%(start, end)])

        if rev is not None:
            cmd.append (rev)
        else:
            try:
                get_config (uri, 'remote.origin.url')
                cmd.append ('origin/master')
            except CommandError:
                pass

        cmd.append ('--')

        # Git doesn't support multiple files
        # we take just the first one
        cmd.append (files and files[0] or uri)

        command = Command (cmd, cwd, env = {'PAGER' : ''})
        self._run_command (command, BLAME)

    def ls (self, uri, rev = None):
        self._check_uri (uri)

        target = None
        if os.path.isfile (uri):
            cwd = os.path.dirname (uri)
            target = os.path.basename (uri)
        elif os.path.isdir (uri):
            cwd = uri
        else:
            cwd = os.getcwd ()

        if rev is None:
            try:
                get_config (uri, 'remote.origin.url')
                rev = 'origin/master'
            except CommandError:
                rev = 'HEAD'

        cmd = ['git',  'ls-tree', '--name-only', '--full-name', '-r', rev]

        if target is not None:
            cmd.append (target)

        command = Command (cmd, cwd, env = {'PAGER' : ''})
        self._run_command (command, LS)

    def get_modules (self):
        #Not supported by Git
        return []

    def get_previous_commit (self, uri, rev, file_name, follow=True):
        self._check_uri (uri)
        
        cmd = ['git', 'log', '--format=%H']
        if follow:
            cmd.append('--follow')
        cmd.extend([rev, '--', file_name])
        command = Command (cmd, uri, env = {'PAGER' : ''})
        
        try:
            out = command.run_sync ()
            return out.splitlines()[1].strip ('\n\t ')
        except:
            return None

    def get_last_revision (self, uri):
        self._check_uri (uri)

        cmd = ['git', 'rev-list', 'HEAD^..HEAD']

        command = Command (cmd, uri, env = {'PAGER' : ''})
        try:
            out = command.run_sync ()
        except:
            return None

        if out == "":
            return None

        return out.strip ('\n\t ')

register_backend ('git', GitRepository)
