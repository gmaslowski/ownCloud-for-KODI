'''
    owncloud XBMC Plugin
    Copyright (C) 2013-2014 ddurdle

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.


'''

import os
import re
import urllib, urllib2
import cookielib
from resources.lib import authorization
from cloudservice import cloudservice
from resources.lib import folder
from resources.lib import file
from resources.lib import package
from resources.lib import mediaurl


import xbmc, xbmcaddon, xbmcgui, xbmcplugin


#
#
#
class owncloud(cloudservice):


    AUDIO = 1
    VIDEO = 2
    PICTURE = 3

    MEDIA_TYPE_MUSIC = 1
    MEDIA_TYPE_VIDEO = 2
    MEDIA_TYPE_PICTURE = 3

    MEDIA_TYPE_FOLDER = 0

    CACHE_TYPE_MEMORY = 0
    CACHE_TYPE_DISK = 1
    CACHE_TYPE_AJAX = 2
    OWNCLOUD_V6 = 0
    OWNCLOUD_V7 = 1

    FILE_URL = 'http://www.firedrive.com/file/'
    DOWNLOAD_LINK = 'http://dl.firedrive.com/?alias='

##
    # initialize (save addon, instance name, user agent)
    ##
    def __init__(self, PLUGIN_URL, addon, instanceName, user_agent):
        self.PLUGIN_URL = PLUGIN_URL
        self.addon = addon
        self.instanceName = instanceName

        try:
            username = self.addon.getSetting(self.instanceName+'_username')
        except:
            username = ''
        self.authorization = authorization.authorization(username)

        try:
            self.version = self.addon.getSetting(self.instanceName+'_version')
        except:
            self.version = OWNCLOUD_V6

        try:
            self.version = self.addon.getSetting(self.instanceName+'_version')
        except:
            self.version = OWNCLOUD_V6

        try:
            protocol = self.addon.getSetting(self.instanceName+'protocol')
            if protocol == 1:
                self.protocol = 'https://'
            else:
                self.protocol = 'http://'
        except:
            self.protocol = 'http://'

        try:
            self.domain = self.addon.getSetting(self.instanceName+'_domain')
        except:
            self.domain = 'localhost'


        self.cookiejar = cookielib.CookieJar()

        try:
            auth = self.addon.getSetting(self.instanceName+'_auth_token')
            session = self.addon.getSetting(self.instanceName+'_auth_session')
        except:
            auth = ''
            session = ''

        self.authorization.setToken('auth_token',auth)
        self.authorization.setToken('auth_session',session)
        self.user_agent = user_agent

        #public playback only -- no authentication
        if self.authorization.username == '':
            return

        # if we have an authorization token set, try to use it
        if auth != '':
          xbmc.log(self.addon.getAddonInfo('name') + ': ' + 'using token', xbmc.LOGDEBUG)
          return
        else:
          xbmc.log(self.addon.getAddonInfo('name') + ': ' + 'no token - logging in', xbmc.LOGDEBUG)
          self.login();
          return


    ##
    # perform login
    ##
    def login(self):

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookiejar))
        # default User-Agent ('Python-urllib/2.6') will *not* work
        opener.addheaders = [('User-Agent', self.user_agent)]

        url = self.protocol + self.domain +'/'

        try:
            response = opener.open(url)

        except urllib2.URLError, e:
            xbmc.log(self.addon.getAddonInfo('name') + ': ' + str(e), xbmc.LOGERROR)
            return
        response_data = response.read()
        response.close()

        requestToken = None

        #owncloud7
        for r in re.finditer('name=\"(requesttoken)\" value\=\"([^\"]+)\"',
                             response_data, re.DOTALL):
            requestTokenType,requestToken = r.groups()

        url = self.protocol + self.domain + '/index.php'


        values = {
                  'password' : self.addon.getSetting(self.instanceName+'_password'),
                  'user' : self.authorization.username,
                  'remember_login' : 1,
                  'requesttoken' : requestToken,
                  'timezone-offset' : -4,
        }

        # try login
        try:
            response = opener.open(url,urllib.urlencode(values))

        except urllib2.URLError, e:
            if e.code == 403:
                #login denied
                xbmcgui.Dialog().ok(self.addon.getLocalizedString(30000), self.addon.getLocalizedString(30017))
                xbmc.log(self.addon.getAddonInfo('name') + ': ' + str(e), xbmc.LOGERROR)
            return
        response_data = response.read()
        response.close()


        loginResult = 0
        #validate successful login
        for r in re.finditer('(data-user)\=\"([^\"]+)\"',
                             response_data, re.DOTALL):
            loginType,loginResult = r.groups()

        if (loginResult == 0 or loginResult != self.authorization.username):
            xbmcgui.Dialog().ok(self.addon.getLocalizedString(30000), self.addon.getLocalizedString(30017))
            xbmc.log(self.addon.getAddonInfo('name') + ': ' + 'login failed', xbmc.LOGERROR)
            return

        for cookie in self.cookiejar:
            for r in re.finditer(' ([^\=]+)\=([^\s]+)\s',
                        str(cookie), re.DOTALL):
                cookieType,cookieValue = r.groups()
                if cookieType == 'oc_token':
                    self.authorization.setToken('auth_token',cookieValue)
                elif cookieType != 'oc_remember_login' and cookieType != 'oc_username':
                    self.authorization.setToken('auth_session',cookieType + '=' + cookieValue)

        return


    ##
    # return the appropriate "headers" for owncloud requests that include 1) user agent, 2) authorization cookie
    #   returns: list containing the header
    ##
    def getHeadersList(self):
        auth = self.authorization.getToken('auth_token')
        session = self.authorization.getToken('auth_session')
        if (auth != '' or session != ''):
            return [('User-Agent', self.user_agent), ('Cookie', session+'; oc_username='+self.authorization.username+'; oc_token='+auth+'; oc_remember_login=1')]
        else:
            return [('User-Agent', self.user_agent )]



    ##
    # return the appropriate "headers" for owncloud requests that include 1) user agent, 2) authorization cookie
    #   returns: URL-encoded header string
    ##
    def getHeadersEncoded(self):
        auth = self.authorization.getToken('auth_token')
        session = self.authorization.getToken('auth_session')

        if (auth != '' or session != ''):
            return urllib.urlencode({ 'User-Agent' : self.user_agent, 'Cookie' : session+'; oc_username='+self.authorization.username+'; oc_token='+auth+'; oc_remember_login=1' })
        else:
            return urllib.urlencode({ 'User-Agent' : self.user_agent })

    ##
    # retrieve a list of videos, using playback type stream
    #   parameters: prompt for video quality (optional), cache type (optional)
    #   returns: list of videos
    ##
    def getMediaList(self, folderName='', cacheType=CACHE_TYPE_MEMORY):

        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookiejar))
        opener.addheaders = self.getHeadersList()

        if (self.version == self.OWNCLOUD_V6):
            url = self.protocol + self.domain +'/index.php/apps/files?' + urllib.urlencode({'dir' : folderName})
        else:
            url = self.protocol + self.domain +'/index.php/apps/files/ajax/list.php?'+ urllib.urlencode({'dir' : folderName})+'&sort=name&sortdirection=asc'


        # if action fails, validate login
        try:
            response = opener.open(url)
        except urllib2.URLError, e:
            self.login()

            try:
                response = opener.open(url)
            except urllib2.URLError, e:
                xbmc.log(self.addon.getAddonInfo('name') + ': ' + str(e), xbmc.LOGERROR)
                return
        response_data = response.read()
        response.close()

#        loginResult = 0
        #validate successful login
#        for r in re.finditer('(data-user)\=\"([^\"]+)\" data-requesttoken="([^\"]+)"',
#                             response_data, re.DOTALL):
#            loginType,loginResult,requestToken = r.groups()

 #       if (loginResult == 0 or loginResult != self.authorization.username):
 #           self.login()
 #           try:
 #               opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookiejar))
#                opener.addheaders = self.getHeadersList()
#                response = opener.open(url)
#                response_data = response.read()
#                response.close()
#            except urllib2.URLError, e:
#                xbmc.log(self.addon.getAddonInfo('name') + ': ' + str(e), xbmc.LOGERROR)
#                return

        mediaFiles = []
        # parsing page for files
        if (self.version == self.OWNCLOUD_V6):

            for r in re.finditer('\<tr data\-id\=.*?</tr>' ,response_data, re.DOTALL):
                entry = r.group()
                for q in re.finditer('data\-id\=\"([^\"]+)\".*?data\-file\=\"([^\"]+)\".*?data\-type\=\"([^\"]+)\".*?data\-mime\=\"([^\/]+)\/' ,entry, re.DOTALL):
                    fileID,fileName,contentType,fileType = q.groups()

                    # Undo any urlencoding before displaying the files (should also make the folders accessible)
                    fileName = urllib.unquote(fileName)

                    if fileType == 'video':
                        fileType = self.MEDIA_TYPE_VIDEO
                    elif fileType == 'audio':
                        fileType = self.MEDIA_TYPE_MUSIC
                    elif fileType == 'image':
                        fileType = self.MEDIA_TYPE_PICTURE


                    if contentType == 'dir':
#                        videos[fileName] = {'url':  'plugin://plugin.video.owncloud?mode=folder&directory=' + urllib.quote_plus(folderName+'/'+fileName), 'mediaType': self.MEDIA_TYPE_FOLDER}
                        mediaFiles.append(package.package(0,folder.folder(folderName+'/'+fileName,fileName)) )
#                    elif cacheType == self.CACHE_TYPE_MEMORY:
#                        videos[fileName] = {'url': self.protocol + self.domain +'/index.php/apps/files/download/'+urllib.quote_plus(folderName)+ '/'+fileName + '|' + self.getHeadersEncoded(), 'mediaType': fileType}
                    #elif cacheType == self.CACHE_TYPE_AJAX:
#                        videos[fileName] = {'url': self.protocol + self.domain +'/index.php/apps/files/ajax/download.php?'+ urllib.urlencode({'dir' : folderName})+'&files='+fileName + '|' + self.getHeadersEncoded(), 'mediaType': fileType}
                    else:
                        mediaFiles.append(package.package(file.file(fileName, fileName, fileName, fileType, '', ''),folder.folder(folderName,folderName)) )

            return mediaFiles
        else:
            for r in re.finditer('\[\{.*?\}\]' ,response_data, re.DOTALL):
                entry = r.group()

                for s in re.finditer('\{.*?\}' ,entry, re.DOTALL):
                    item = s.group()

                    for q in re.finditer('\"id\"\:\"([^\"]+)\".*?\"name\"\:\"([^\"]+)\".*?\"mimetype\"\:\"([^\/]+)\/.*?\"type\"\:\"([^\"]+)\"' ,item, re.DOTALL):
                        fileID,fileName,fileType,contentType = q.groups()

                        # Undo any urlencoding before displaying the files (should also make the folders accessible)
                        fileName = urllib.unquote(fileName)

                        if fileType == 'video\\':
                            fileType = self.MEDIA_TYPE_VIDEO
                        elif fileType == 'audio\\':
                            fileType = self.MEDIA_TYPE_MUSIC
                        elif fileType == 'image\\':
                            fileType = self.MEDIA_TYPE_PICTURE

#                        if contentType == 'dir':
#                            videos[fileName] = {'url':  'plugin://plugin.video.owncloud?mode=folder&directory=' + urllib.quote_plus(folderName+'/'+fileName), 'mediaType': self.MEDIA_TYPE_FOLDER}
#                        elif cacheType == self.CACHE_TYPE_MEMORY:
#                            videos[fileName] = {'url': self.protocol + self.domain +'/index.php/apps/files/download/'+urllib.quote_plus(folderName)+ '/'+fileName + '|' + self.getHeadersEncoded(), 'mediaType': fileType}
#                        elif cacheType == self.CACHE_TYPE_AJAX:
#                            videos[fileName] = {'url': self.protocol + self.domain +'/index.php/apps/files/ajax/download.php?'+ urllib.urlencode({'dir' : folderName})+'&files='+fileName + '|' + self.getHeadersEncoded(), 'mediaType': fileType}
                        if contentType == 'dir':
                            mediaFiles.append(package.package(0,folder.folder(folderName+'/'+fileName,fileName)) )
                        else:
                            mediaFiles.append(package.package(file.file(fileName, fileName, fileName, fileType, '', ''),folder.folder(folderName,folderName)) )

            return mediaFiles


    ##
    # retrieve a playback url
    #   returns: url
    ##
    def getPlaybackCall(self, playbackType, package):
        if playbackType == self.CACHE_TYPE_AJAX:
            params = urllib.urlencode({'files': package.file.id, 'dir': package.folder.id})
            return self.protocol + self.domain +'/index.php/apps/files/ajax/download.php?'+params + '|' + self.getHeadersEncoded()
        else:
            return self.protocol + self.domain +'/index.php/apps/files/download/'+urllib.quote(package.folder.id)+ '/'+urllib.quote(package.file.id) + '|' + self.getHeadersEncoded()

    ##
    # retrieve a media url
    #   returns: url
    ##
    def getMediaCall(self, package):
        if package.file.type == package.file.VIDEO:
            return self.PLUGIN_URL+'?mode=video&filename='+package.file.id+'&title='+package.file.title+'&directory=' + package.folder.id
        elif package.file.type == package.file.AUDIO:
            return self.PLUGIN_URL+'?mode=audio&filename='+package.file.id+'&title='+package.file.title+'&directory=' + package.folder.id
        else:
            return self.PLUGIN_URL+'?mode=audio&filename='+package.file.id+'&title='+package.file.title+'&directory=' + package.folder.id


    ##
    # retrieve a directory url
    #   returns: url
    ##
    def getDirectoryCall(self, folder):
#                        videos[fileName] = {'url':  'plugin://plugin.video.owncloud?mode=folder&directory=' + urllib.quote_plus(folderName+'/'+fileName), 'mediaType': self.MEDIA_TYPE_FOLDER}

        return self.PLUGIN_URL+'?mode=folder&instance='+self.instanceName+'&directory=' + folder.id


