# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <http://unlicense.org>

cmake_minimum_required(VERSION 2.8)

project("sonic-cli")
set(PROJECT_VERSION "0.99")
set(PROJECT_DESCRIPTION "SONIC CLI library")

include(GNUInstallDirs)
include(FindPkgConfig)

pkg_check_modules(LIBCAP REQUIRED libcap)

add_definitions(-DHAVE_CONFIG_H -DSYSCONFDIR="${CMAKE_INSTALL_SYSCONFDIR}")

set (CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -std=gnu99 -Wall -Werror")

include_directories(
  ${CMAKE_SOURCE_DIR}
  ${CMAKE_SOURCE_DIR}/lib
  ${PROJECT_SOURCE_DIR})

set (CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -std=gnu99 -Wall -Werror")

add_custom_command(
  OUTPUT gitversion.h
  COMMAND perl gitversion.pl ${CMAKE_SOURCE_DIR} > gitversion.h 2> /dev/null
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

add_custom_command(
  OUTPUT route_types.h
  COMMAND perl route_types.pl < route_types.txt > route_types.h
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

add_custom_command(
  OUTPUT memtypes.h
  COMMAND gawk -f memtypes.awk memtypes.c > memtypes.h
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR})

add_library(sonic-cli SHARED
  gitversion.h route_types.h memtypes.h network.c getopt.c getopt1.c daemon.c
  checksum.c vector.c linklist.c vty.c command.c sockunion.c prefix.c thread.c
  if.c memory.c buffer.c table.c hash.c routemap.c distribute.c
  stream.c str.c log.c plist.c zclient.c sockopt.c smux.c agentx.c
  snmp.c md5.c if_rmap.c keychain.c privs.c sigevent.c pqueue.c jhash.c
  memtypes.c workqueue.c filter.c rbac.c authorization.c)

target_link_libraries(sonic-cli PUBLIC ${LIBCAP_LIBRARIES} crypt tac)
target_include_directories (sonic-cli PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
set_target_properties(sonic-cli PROPERTIES VERSION "0")
set_target_properties(sonic-cli PROPERTIES SOVERSION "0.0.0")

set(PKG_CONFIG_LIBDIR "\${prefix}/lib")
set(PKG_CONFIG_INCLUDEDIR "\${prefix}/include/vtysh")
set(PKG_CONFIG_LIBS "-L\${libdir} -lsonic-cli")
set(PKG_CONFIG_CFLAGS "-I\${includedir}")

configure_file(
  "${CMAKE_CURRENT_SOURCE_DIR}/pkg-config.pc.cmake"
  "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.pc")

install(
  FILES "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.pc"
  DESTINATION "/usr/lib/pkgconfig")
install(
  TARGETS sonic-cli
  LIBRARY DESTINATION "/usr/lib")
install(
  FILES
  buffer.h checksum.h command.h distribute.h config.h filter.h getopt.h
  hash.h if.h if_rmap.h jhash.h keychain.h libospf.h
  linklist.h log.h md5.h memory.h memtypes.h network.h plist.h pqueue.h prefix.h
  privs.h queue.h routemap.h regex-gnu.h sigevent.h smux.h sockopt.h sockunion.h stream.h
  str.h table.h thread.h vector.h vty.h workqueue.h zassert.h
  zclient.h zebra.h rbac.h authorization.h
  DESTINATION "${CMAKE_INSTALL_FULL_INCLUDEDIR}/vtysh")

# TODO(bluecmd): We're shipping version.h because projects like to include it
# but we're not shipping gitversion - so what's the point?
install(
  FILES version.h memtypes.h route_types.h
  DESTINATION "${CMAKE_INSTALL_FULL_INCLUDEDIR}/vtysh/lib")
