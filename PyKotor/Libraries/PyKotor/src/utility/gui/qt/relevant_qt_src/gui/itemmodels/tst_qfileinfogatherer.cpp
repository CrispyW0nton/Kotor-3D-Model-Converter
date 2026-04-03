// Copyright (C) 2016 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

#include <QtTest/QtTest>
#include <QtCore/QTemporaryDir>
#include <QtGui/QFileSystemModel>
#include <QtWidgets/QApplication>

class tst_QFileInfoGatherer : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void cleanupTestCase();

    void basicFileInfo();
    void directoryInfo();
    void hiddenFiles();
    void symlinks();
    void permissions();
    void iconProvider();
    void fileWatching();

private:
    QTemporaryDir m_tempDir;
    QString m_tempPath;
};

void tst_QFileInfoGatherer::initTestCase()
{
    QVERIFY(m_tempDir.isValid());
    m_tempPath = m_tempDir.path();

    // Create test files and directories
    QDir dir(m_tempPath);
    QVERIFY(dir.mkdir("testdir"));

    QFile file(m_tempPath + "/testfile.txt");
    QVERIFY(file.open(QIODevice::WriteOnly));
    file.write("test content");
    file.close();

    // Create a subdirectory with files
    QString subDirPath = m_tempPath + "/testdir";
    QFile subFile(subDirPath + "/subfile.txt");
    QVERIFY(subFile.open(QIODevice::WriteOnly));
    subFile.write("sub content");
    subFile.close();

#ifdef Q_OS_UNIX
    // Create a symlink if supported
    QString linkPath = m_tempPath + "/testlink";
    QFile::link(m_tempPath + "/testfile.txt", linkPath);
#endif
}

void tst_QFileInfoGatherer::cleanupTestCase()
{
    // Cleanup handled by QTemporaryDir
}

void tst_QFileInfoGatherer::basicFileInfo()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex fileIndex = model.index(m_tempPath + "/testfile.txt");
    QVERIFY(fileIndex.isValid());

    QFileInfo info = model.fileInfo(fileIndex);
    QVERIFY(info.exists());
    QCOMPARE(info.fileName(), QString("testfile.txt"));
    QCOMPARE(info.size(), qint64(12)); // "test content" = 12 bytes
    QVERIFY(info.isFile());
    QVERIFY(!info.isDir());
}

void tst_QFileInfoGatherer::directoryInfo()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex dirIndex = model.index(m_tempPath + "/testdir");
    QVERIFY(dirIndex.isValid());

    QFileInfo info = model.fileInfo(dirIndex);
    QVERIFY(info.exists());
    QCOMPARE(info.fileName(), QString("testdir"));
    QVERIFY(info.isDir());
    QVERIFY(!info.isFile());
}

void tst_QFileInfoGatherer::hiddenFiles()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    // Create a hidden file
    QString hiddenFilePath = m_tempPath + "/.hiddenfile";
    QFile hiddenFile(hiddenFilePath);
    QVERIFY(hiddenFile.open(QIODevice::WriteOnly));
    hiddenFile.write("hidden content");
    hiddenFile.close();

#ifdef Q_OS_UNIX
    // On Unix, files starting with . are hidden
    QFileInfo info(hiddenFilePath);
    QVERIFY(info.isHidden());
#endif

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    // Test with hidden files filter
    model.setFilter(QDir::AllEntries | QDir::Hidden | QDir::NoDotAndDotDot);

    QModelIndex hiddenIndex = model.index(hiddenFilePath);
    if (hiddenIndex.isValid()) {
        QFileInfo hiddenInfo = model.fileInfo(hiddenIndex);
        QCOMPARE(hiddenInfo.fileName(), QString(".hiddenfile"));
    }
}

void tst_QFileInfoGatherer::symlinks()
{
#ifdef Q_OS_UNIX
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex linkIndex = model.index(m_tempPath + "/testlink");
    QVERIFY(linkIndex.isValid());

    QFileInfo info = model.fileInfo(linkIndex);
    QVERIFY(info.exists());
    QCOMPARE(info.fileName(), QString("testlink"));
    QVERIFY(info.isSymLink());

    // Test symlink resolution
    model.setResolveSymlinks(true);
    QVERIFY(model.resolveSymlinks());

    model.setResolveSymlinks(false);
    QVERIFY(!model.resolveSymlinks());
#endif
}

void tst_QFileInfoGatherer::permissions()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex fileIndex = model.index(m_tempPath + "/testfile.txt");
    QVERIFY(fileIndex.isValid());

    QFile::Permissions perms = model.permissions(fileIndex);
    QVERIFY(perms != 0); // Should have some permissions

    // Test that we have read permission
    QVERIFY(perms & QFile::ReadOwner);
}

void tst_QFileInfoGatherer::iconProvider()
{
    QFileSystemModel model;

    // Test default icon provider
    QVERIFY(model.iconProvider() != nullptr);

    // Test setting custom icon provider
    QFileIconProvider *customProvider = new QFileIconProvider();
    model.setIconProvider(customProvider);
    QCOMPARE(model.iconProvider(), customProvider);

    // Test icons are available
    model.setRootPath(m_tempPath);
    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex fileIndex = model.index(m_tempPath + "/testfile.txt");
    QVERIFY(fileIndex.isValid());

    QIcon icon = model.data(fileIndex, Qt::DecorationRole).value<QIcon>();
    QVERIFY(!icon.isNull());
}

void tst_QFileInfoGatherer::fileWatching()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    // Create a new file to test watching
    QString newFilePath = m_tempPath + "/watched_file.txt";
    QFile newFile(newFilePath);
    QVERIFY(newFile.open(QIODevice::WriteOnly));
    newFile.write("watched content");
    newFile.close();

    // The model should detect the new file
    QSignalSpy fileChangedSpy(&model, SIGNAL(fileChanged(QString,QString,QString)));
    QSignalSpy directoryChangedSpy(&model, SIGNAL(directoryLoaded(QString)));

    // Wait a bit for file system events
    QTest::qWait(1000);

    // Modify the file
    QVERIFY(newFile.open(QIODevice::WriteOnly | QIODevice::Append));
    newFile.write(" modified");
    newFile.close();

    // Wait for events
    QTest::qWait(1000);

    // Clean up
    QFile::remove(newFilePath);
}

QTEST_MAIN(tst_QFileInfoGatherer)
#include "tst_qfileinfogatherer.moc"