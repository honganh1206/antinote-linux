import QtQuick

Item {
    id: root
    visible: backend && backend.timerVisible
    width: 136
    height: 42
    z: 20

    Rectangle {
        anchors.fill: parent
        radius: 8
        color: backend ? backend.colors.bg : "#1f2023"
        border.width: 1
        border.color: backend ? backend.colors.muted : "#6f6b64"
        opacity: 0.96
    }

    Text {
        id: timeLabel
        anchors.left: parent.left
        anchors.leftMargin: 12
        anchors.verticalCenter: parent.verticalCenter
        text: backend ? backend.timerDisplay : "00:00"
        color: backend ? backend.colors.text : "#d6d3cc"
        font.family: backend ? backend.font.family : ""
        font.pixelSize: backend ? backend.font.size : 15
        font.bold: true
    }

    Text {
        anchors.left: timeLabel.right
        anchors.leftMargin: 7
        anchors.verticalCenter: parent.verticalCenter
        text: !backend || backend.timerState === "running" ? "" : backend.timerState
        color: backend ? backend.colors.muted : "#6f6b64"
        font.family: backend ? backend.font.family : ""
        font.pixelSize: backend ? backend.font.size - 4 : 11
    }

    MouseArea {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 24
        height: 24
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: backend.dismiss_timer()

        Text {
            anchors.centerIn: parent
            text: "×"
            color: parent.containsMouse && backend ? backend.colors.text : (backend ? backend.colors.muted : "#6f6b64")
            font.pixelSize: 16
        }
    }
}
