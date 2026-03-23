// Copyright (C) 2016 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

#include <QtTest/QtTest>
#include <QtCore/QTemporaryDir>
#include <QtCore/QTemporaryFile>
#include <QtCore/QFileSystemWatcher>

class tst_QFileSystemWatcher : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void cleanupTestCase();

    void addPath();
    void addPaths();
    void removePath();
    void removePaths();
    void files();
    void directories();
    void fileChanged();
    void directoryChanged();
    void multipleWatchers();

private:
    QTemporaryDir m_tempDir;
    QString m_tempPath;
};

void tst_QFileSystemWatcher::initTestCase()
{
    QVERIFY(m_tempDir.isValid());
    m_tempPath = m_tempDir.path();
}

void tst_QFileSystemWatcher::cleanupTestCase()
{
    // Cleanup handled by QTemporaryDir
}

void tst_QFileSystemWatcher::addPath()
{
    QFileSystemWatcher watcher;
    QString filePath = m_tempPath + "/test_add_path.txt";

    // Create a test file
    QFile file(filePath);
    QVERIFY(file.open(QIODevice::WriteOnly));
    file.write("test content");
    file.close();

    // Test adding path
    bool added = watcher.addPath(filePath);
    QVERIFY(added);

    // Verify it's in the files list
    QStringList files = watcher.files();
    QVERIFY(files.contains(filePath));
}

void tst_QFileSystemWatcher::addPaths()
{
    QFileSystemWatcher watcher;

    QStringList paths;
    paths << (m_tempPath + "/test_add_paths1.txt")
          << (m_tempPath + "/test_add_paths2.txt");

    // Create test files
    for (const QString &path : paths) {
        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("test content");
        file.close();
    }

    // Test adding multiple paths
    QStringList addedPaths = watcher.addPaths(paths);
    QVERIFY(addedPaths.isEmpty()); // Should succeed for all

    // Verify all are in the files list
    QStringList files = watcher.files();
    for (const QString &path : paths) {
        QVERIFY(files.contains(path));
    }
}

void tst_QFileSystemWatcher::removePath()
{
    QFileSystemWatcher watcher;
    QString filePath = m_tempPath + "/test_remove_path.txt";

    // Create and add a test file
    QFile file(filePath);
    QVERIFY(file.open(QIODevice::WriteOnly));
    file.write("test content");
    file.close();

    watcher.addPath(filePath);
    QVERIFY(watcher.files().contains(filePath));

    // Test removing path
    bool removed = watcher.removePath(filePath);
    QVERIFY(removed);

    // Verify it's no longer in the files list
    QStringList files = watcher.files();
    QVERIFY(!files.contains(filePath));
}

void tst_QFileSystemWatcher::removePaths()
{
    QFileSystemWatcher watcher;

    QStringList paths;
    paths << (m_tempPath + "/test_remove_paths1.txt")
          << (m_tempPath + "/test_remove_paths2.txt");

    // Create and add test files
    for (const QString &path : paths) {
        QFile file(path);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("test content");
        file.close();
        watcher.addPath(path);
    }

    QVERIFY(watcher.files().size() >= 2);

    // Test removing multiple paths
    QStringList removedPaths = watcher.removePaths(paths);
    QVERIFY(removedPaths.isEmpty()); // Should succeed for all

    // Verify none are in the files list
    QStringList files = watcher.files();
    for (const QString &path : paths) {
        QVERIFY(!files.contains(path));
    }
}

void tst_QFileSystemWatcher::files()
{
    QFileSystemWatcher watcher;

    QStringList testFiles;
    testFiles << (m_tempPath + "/test_files1.txt")
              << (m_tempPath + "/test_files2.txt");

    // Create and add test files
    for (const QString &filePath : testFiles) {
        QFile file(filePath);
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("test content");
        file.close();
        watcher.addPath(filePath);
    }

    QStringList files = watcher.files();
    QCOMPARE(files.size(), testFiles.size());

    for (const QString &filePath : testFiles) {
        QVERIFY(files.contains(filePath));
    }
}

void tst_QFileSystemWatcher::directories()
{
    QFileSystemWatcher watcher;

    QString dirPath = m_tempPath + "/test_watch_dir";
    QDir().mkdir(dirPath);

    watcher.addPath(dirPath);

    QStringList directories = watcher.directories();
    QVERIFY(directories.contains(dirPath));
}

void tst_QFileSystemWatcher::fileChanged()
{
    QFileSystemWatcher watcher;
    QString filePath = m_tempPath + "/test_file_changed.txt";

    // Create a test file
    QFile file(filePath);
    QVERIFY(file.open(QIODevice::WriteOnly));
    file.write("initial content");
    file.close();

    watcher.addPath(filePath);

    QSignalSpy fileChangedSpy(&watcher, SIGNAL(fileChanged(QString)));

    // Modify the file
    QVERIFY(file.open(QIODevice::WriteOnly | QIODevice::Truncate));
    file.write("modified content");
    file.close();

    // Wait for the signal (may take some time on some systems)
    QTRY_VERIFY(fileChangedSpy.count() > 0);

    QCOMPARE(fileChangedSpy.at(0).at(0).toString(), filePath);
}

void tst_QFileSystemWatcher::directoryChanged()
{
    QFileSystemWatcher watcher;
    QString dirPath = m_tempPath + "/test_dir_changed";
    QDir().mkdir(dirPath);

    watcher.addPath(dirPath);

    QSignalSpy dirChangedSpy(&watcher, SIGNAL(directoryChanged(QString)));

    // Create a file in the watched directory
    QString newFilePath = dirPath + "/new_file.txt";
    QFile file(newFilePath);
    QVERIFY(file.open(QIODevice::WriteOnly));
    file.write("test");
    file.close();

    // Wait for the signal
    QTRY_VERIFY(dirChangedSpy.count() > 0);

    QCOMPARE(dirChangedSpy.at(0).at(0).toString(), dirPath);
}

void tst_QFileSystemWatcher::multipleWatchers()
{
    QFileSystemWatcher watcher1;
    QFileSystemWatcher watcher2;

    QString filePath = m_tempPath + "/test_multiple_watchers.txt";

    // Create a test file
    QFile file(filePath);
    QVERIFY(file.open(QIODevice::WriteOnly));
    file.write("test");
    file.close();

    // Add the same file to both watchers
    watcher1.addPath(filePath);
    watcher2.addPath(filePath);

    QSignalSpy spy1(&watcher1, SIGNAL(fileChanged(QString)));
    QSignalSpy spy2(&watcher2, SIGNAL(fileChanged(QString)));

    // Modify the file
    QVERIFY(file.open(QIODevice::WriteOnly | QIODevice::Truncate));
    file.write("modified");
    file.close();

    // Both watchers should receive the signal
    QTRY_VERIFY(spy1.count() > 0);
    QTRY_VERIFY(spy2.count() > 0);

    QCOMPARE(spy1.at(0).at(0).toString(), filePath);
    QCOMPARE(spy2.at(0).at(0).toString(), filePath);
}

QTEST_MAIN(tst_QFileSystemWatcher)
#include "tst_qfilesystemwatcher.moc"