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

project("cli")

include(GNUInstallDirs)
include(FindPkgConfig)

add_definitions(-DHAVE_CONFIG_H -DSYSCONFDIR="${CMAKE_INSTALL_SYSCONFDIR}")

MESSAGE(STATUS "wwww ROUTING_STACK: $ENV{ROUTING_STACK}")

set (CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -std=gnu99 -Wall -Werror -DFTR_PROXY_ARP -DFTR_LOCAL_PROXY_ARP")

include_directories(
  ${CMAKE_SOURCE_DIR}
  ${CMAKE_SOURCE_DIR}/lib
  ${PROJECT_SOURCE_DIR}
  ${SONICCLI_INCLUDE_DIRS}
  )

add_executable(cli
  vtysh_main.c vtysh.c vtysh_user.c vtysh_config.c vtysh_cmd.c vtysh_show.c vtysh_linux.c
  vtysh_dhcp.c vtysh_if.c vtysh_upgrade.c vtysh_arp.c vtysh_bgp.c)

target_link_libraries(cli PUBLIC
  ${SONICCLI_LIBRARIES}
  crypt pthread readline sonic-cli audit)

install(
  TARGETS cli
  RUNTIME DESTINATION "/usr/bin/")

install(
  FILES
  banner
  DESTINATION "/etc/sonic/")

install(
  FILES
  vtysh.h vtysh_user.h
  DESTINATION "${CMAKE_INSTALL_FULL_INCLUDEDIR}/vtysh")
