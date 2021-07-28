#
#  GSC-18128-1, "Core Flight Executive Version 6.7"
#
#  Copyright (c) 2006-2019 United States Government as represented by
#  the Administrator of the National Aeronautics and Space Administration.
#  All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
#!/usr/bin/env python3
#
import csv
import getopt
import mmap
import sys
from pathlib import Path
from struct import unpack

import zmq
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (QApplication, QDialog, QHeaderView,
                             QTableWidgetItem)

from UiGenerictelemetrydialog import UiGenerictelemetrydialog

# ../cFS/tools/cFS-GroundSystem/Subsystems/tlmGUI
ROOTDIR = Path(sys.argv[0]).resolve().parent


class SubsystemTelemetry(QDialog, UiGenerictelemetrydialog):
    #
    # Init the class
    #
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        with open("/tmp/OffsetData", "r+b") as f:
            self.mm = mmap.mmap(f.fileno(), 0, prot=mmap.PROT_READ)

    #
    # This method decodes a telemetry item from the packet and displays it
    #
    def display_telemetry_item(self, datagram, tlm_index, label_field, value_field):
        if tlm_item_is_valid[tlm_index]:
            tlm_offset = 0
            try:
                tlm_offset = self.mm[0]
            except ValueError:
                pass
            tlm_field1 = tlmItemFormat[tlm_index]
            if tlm_field1[0] == "<":
                tlm_field1 = tlm_field1[1:]
            try:
                item_start = int(tlm_item_start[tlm_index]) + tlm_offset
            except UnboundLocalError:
                pass
            tlm_field2 = datagram[item_start:item_start +
                                 int(tlmItemSize[tlm_index])]
            if tlm_field2:
                tlm_field = unpack(tlm_field1, tlm_field2)
                if tlm_item_display_type[tlm_index] == 'Dec':
                    value_field.setText(str(tlm_field[0]))
                elif tlm_item_display_type[tlm_index] == 'Hex':
                    value_field.setText(hex(tlm_field[0]))
                elif tlm_item_display_type[tlm_index] == 'Enm':
                    value_field.setText(tlmItemEnum[tlm_index][int(tlm_field[0])])
                elif tlm_item_display_type[tlm_index] == 'Str':
                    value_field.setText(tlm_field[0].decode('utf-8', 'ignore'))
                label_field.setText(tlmItemDesc[tlm_index])
            else:
                print("ERROR: Can't unpack buffer of length", len(tlm_field2))

    # Start the telemetry receiver (see GTTlmReceiver class)
    def init_gt_tlm_receiver(self, subscr):
        self.setWindowTitle(f"{page_title} for: {subscr}")
        self.thread = GTTlmReceiver(subscr)
        self.thread.gtSignalTlmDatagram.connect(self.process_pending_datagrams)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    #
    # This method processes packets.
    # Called when the TelemetryReceiver receives a message/packet
    #
    def process_pending_datagrams(self, datagram):
        #
        # Show sequence number
        #
        packet_seq = unpack(">H", datagram[2:4])
        seq_count = packet_seq[0] & 0x3FFF  ## sequence count mask
        self.sequence_count.setValue(seq_count)

        #
        # Decode and display all packet elements
        #
        for k in range(self.tbl_telemetry.rowCount()):
            item_label = self.tbl_telemetry.item(k, 0)
            item_value = self.tbl_telemetry.item(k, 1)
            self.display_telemetry_item(datagram, k, item_label, item_value)

    # Reimplements closeEvent
    # to properly quit the thread
    # and close the window
    def closeEvent(self, event):
        self.thread.runs = False
        self.thread.wait(2000)
        self.mm.close()
        super().closeEvent(event)


# Subscribes and receives zeroMQ messages
class GTTlmReceiver(QThread):
    # Setup signal to communicate with front-end GUI
    gtSignalTlmDatagram = pyqtSignal(bytes)

    def __init__(self, subscr):
        super().__init__()
        self.runs = True

        # Init zeroMQ
        context = zmq.Context()
        self.subscriber = context.socket(zmq.SUB)
        self.subscriber.connect("ipc:///tmp/GroundSystem")
        my_tlm_pg_apid = subscr.split(".", 1)
        my_subscription = f"GroundSystem.Spacecraft1.TelemetryPackets.{my_tlm_pg_apid[1]}"
        self.subscriber.setsockopt_string(zmq.SUBSCRIBE, my_subscription)

    def run(self):
        while self.runs:
            # Read envelope with address
            _, datagram = self.subscriber.recv_multipart()
            # Send signal with received packet to front-end/GUI
            self.gtSignalTlmDatagram.emit(datagram)


#
# Display usage
#
def usage():
    print(("Must specify --title=\"<page name>\" --port=<udp_port> "
           "--appid=<packet_app_id(hex)> --endian=<endian(L|B) "
           "--file=<tlm_def_file>\n\nexample: --title=\"Executive Services\" "
           "--port=10800 --appid=800 --file=cfe-es-hk-table.txt --endian=L"))


#
# Main
#
if __name__ == '__main__':
    #
    # Set defaults for the arguments
    #
    page_title = "Telemetry Page"
    # udpPort = 10000
    app_id = 999
    tlm_def_file = f"{ROOTDIR}/telemetry_def.txt"
    endian = "L"
    subscription = ""

    #
    # process cmd line args
    #
    try:
        opts, args = getopt.getopt(
            sys.argv[1:], "htpafl",
            ["help", "title=", "port=", "appid=", "file=", "endian=", "sub="])
    except getopt.GetoptError:
        usage()
        sys.exit(2)

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage()
            sys.exit()
        elif opt in ("-p", "--port"):
            pass
        elif opt in ("-t", "--title"):
            page_title = arg
        elif opt in ("-f", "--file"):
            tlm_def_file = arg
        elif opt in ("-t", "--appid"):
            app_id = arg
        elif opt in ("-e", "--endian"):
            endian = arg
        elif opt in ("-s", "--sub"):
            subscription = arg

    if not subscription:
        subscription = "GroundSystem"

    print('Generic Telemetry Page started. Subscribed to', subscription)

    py_endian = '<' if endian.upper() == 'L' else '>'

    #
    # Init the QT application and the telemetry class
    #
    app = QApplication(sys.argv)
    telem = SubsystemTelemetry()
    tbl = telem.tbl_telemetry
    telem.sub_system_line_edit.setText(page_title)
    telem.packet_id.display(app_id)

    #
    # Read in the contents of the telemetry packet definition
    #
    tlm_item_is_valid, tlmItemDesc, \
    tlm_item_start, tlmItemSize, \
    tlm_item_display_type, tlmItemFormat = ([] for _ in range(6))

    tlmItemEnum = [None] * 40

    i = 0
    with open(f"{ROOTDIR}/{tlm_def_file}") as tlmfile:
        reader = csv.reader(tlmfile, skipinitialspace=True)
        for row in reader:
            if not row[0].startswith("#"):
                tlm_item_is_valid.append(True)
                tlmItemDesc.append(row[0])
                tlm_item_start.append(row[1])
                tlmItemSize.append(row[2])
                if row[3].lower() == 's':
                    tlmItemFormat.append(f'{row[2]}{row[3]}')
                else:
                    tlmItemFormat.append(f'{py_endian}{row[3]}')
                tlm_item_display_type.append(row[4])
                if row[4] == 'Enm':
                    tlmItemEnum[i] = row[5:9]
                telem.tbl_telemetry.insertRow(i)
                lblItem, valItem = QTableWidgetItem(), QTableWidgetItem()
                telem.tbl_telemetry.setItem(i, 0, lblItem)
                telem.tbl_telemetry.setItem(i, 1, valItem)
                i += 1
    tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    tbl.verticalHeader().setSectionResizeMode(QHeaderView.Stretch)

    #
    # Display the page
    #
    telem.show()
    telem.raise_()
    telem.init_gt_tlm_receiver(subscription)

    sys.exit(app.exec_())
