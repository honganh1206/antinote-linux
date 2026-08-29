import QtQuick

Item {
    id: root
    visible: backend && backend.timerVisible
    width: 34
    z: 20

    readonly property int blockCount: 28
    readonly property real progress: !backend || backend.timerTotal <= 0
        ? 0
        : Math.min(1, backend.timerElapsed / backend.timerTotal)
    readonly property int fadedBlocks: Math.floor(progress * blockCount)

    function formatDuration(milliseconds) {
        const seconds = Math.floor(Math.max(0, milliseconds) / 1000)
        const minutes = Math.floor(seconds / 60)
        return (minutes < 10 ? "0" : "") + minutes + ":"
            + (seconds % 60 < 10 ? "0" : "") + (seconds % 60)
    }

    Text {
        id: elapsedLabel
        anchors.top: parent.top
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.formatDuration(backend ? backend.timerElapsed : 0)
        color: backend ? backend.colors.muted : "#6f6b64"
        opacity: backend && backend.timerState === "paused" ? 0.55 : 1
        font.family: backend ? backend.font.family : ""
        font.pixelSize: 10
    }

    Item {
        id: blocks
        anchors.top: elapsedLabel.bottom
        anchors.topMargin: 8
        anchors.bottom: totalLabel.top
        anchors.bottomMargin: 8
        anchors.horizontalCenter: parent.horizontalCenter
        width: 3

        Repeater {
            model: root.blockCount
            delegate: Rectangle {
                width: 3
                height: 3
                radius: 1
                y: index * (blocks.height - height) / Math.max(1, root.blockCount - 1)
                color: index < root.fadedBlocks
                    ? (backend ? backend.colors.muted : "#6f6b64")
                    : (backend ? backend.colors.green : "#84c08a")
                opacity: index < root.fadedBlocks ? 0.28 : 1

                Behavior on color { ColorAnimation { duration: 150 } }
                Behavior on opacity { NumberAnimation { duration: 150 } }
            }
        }
    }

    Text {
        id: totalLabel
        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.formatDuration(backend ? backend.timerTotal : 0)
        color: backend ? backend.colors.muted : "#6f6b64"
        font.family: backend ? backend.font.family : ""
        font.pixelSize: 10
    }

    MouseArea {
        anchors.top: parent.top
        anchors.right: parent.right
        width: 16
        height: 16
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        Accessible.name: "Dismiss timer"
        onClicked: backend.dismiss_timer()

        Text {
            anchors.centerIn: parent
            text: "×"
            visible: parent.containsMouse
            color: backend ? backend.colors.text : "#d6d3cc"
            font.pixelSize: 14
        }
    }
}
