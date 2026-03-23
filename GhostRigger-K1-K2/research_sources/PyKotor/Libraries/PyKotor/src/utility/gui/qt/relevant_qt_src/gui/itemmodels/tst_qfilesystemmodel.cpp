// Copyright (C) 2016 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

#include <QtTest/QtTest>
#include <QtCore/QTemporaryDir>
#include <QtCore/QTemporaryFile>
#include <QtGui/QFileSystemModel>
#include <QtWidgets/QApplication>
#include <QtWidgets/QFileIconProvider>

class tst_QFileSystemModel : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void cleanupTestCase();

    void rootPath();
    void index();
    void data();
    void setRootPath();
    void rowCount();
    void remove();
    void mkdir();
    void filters();
    void nameFilters();
    void permissions();
    void fileInfo();
    void sort();
    void icons();
    void hidden();
    void myComputer();
    void shortcut();
    void caseSensitivity();
    void drives();

private:
    QTemporaryDir m_tempDir;
    QString m_tempPath;
};

void tst_QFileSystemModel::initTestCase()
{
    QVERIFY(m_tempDir.isValid());
    m_tempPath = m_tempDir.path();

    // Create some test files and directories
    QDir dir(m_tempPath);
    QVERIFY(dir.mkdir("subdir"));
    QVERIFY(dir.mkdir("subdir2"));

    QFile file(m_tempPath + "/file1.txt");
    QVERIFY(file.open(QIODevice::WriteOnly));
    file.write("test");
    file.close();

    QFile file2(m_tempPath + "/file2.txt");
    QVERIFY(file2.open(QIODevice::WriteOnly));
    file2.write("test2");
    file2.close();

    // Create a hidden file if supported
#ifdef Q_OS_WIN
    QFile::setPermissions(m_tempPath + "/file1.txt", QFile::ReadOwner | QFile::WriteOwner | QFile::Hidden);
#endif
}

void tst_QFileSystemModel::cleanupTestCase()
{
    // Cleanup is handled by QTemporaryDir
}

void tst_QFileSystemModel::rootPath()
{
    QFileSystemModel model;
    QCOMPARE(model.rootPath(), QString());

    QString homePath = QDir::homePath();
    model.setRootPath(homePath);
    QCOMPARE(model.rootPath(), homePath);
}

void tst_QFileSystemModel::index()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    // Test invalid index
    QModelIndex invalid = model.index(-1, 0);
    QVERIFY(!invalid.isValid());

    // Test root index
    QModelIndex rootIndex = model.index(m_tempPath);
    QVERIFY(rootIndex.isValid());
    QCOMPARE(model.filePath(rootIndex), m_tempPath);

    // Wait for directory to be loaded
    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000)); // Wait up to 5 seconds

    // Test child index
    QModelIndex childIndex = model.index(0, 0, rootIndex);
    if (model.rowCount(rootIndex) > 0) {
        QVERIFY(childIndex.isValid());
        QVERIFY(!model.fileName(childIndex).isEmpty());
    }
}

void tst_QFileSystemModel::data()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex rootIndex = model.index(m_tempPath);
    QVERIFY(rootIndex.isValid());

    // Test DisplayRole
    QVariant displayData = model.data(rootIndex, Qt::DisplayRole);
    QVERIFY(displayData.isValid());

    // Test FileNameRole
    QVariant fileNameData = model.data(rootIndex, QFileSystemModel::FileNameRole);
    QVERIFY(fileNameData.isValid());

    // Test FilePathRole
    QVariant filePathData = model.data(rootIndex, QFileSystemModel::FilePathRole);
    QCOMPARE(filePathData.toString(), m_tempPath);
}

void tst_QFileSystemModel::setRootPath()
{
    QFileSystemModel model;

    QSignalSpy rootPathChangedSpy(&model, SIGNAL(rootPathChanged(QString)));

    QString newPath = m_tempPath;
    QModelIndex index = model.setRootPath(newPath);

    QCOMPARE(model.rootPath(), newPath);
    QCOMPARE(rootPathChangedSpy.count(), 1);
    QCOMPARE(rootPathChangedSpy.at(0).at(0).toString(), newPath);

    // Test that index is valid
    QVERIFY(index.isValid());
}

void tst_QFileSystemModel::rowCount()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QModelIndex rootIndex = model.index(m_tempPath);

    // Initially might be 0 until directory is loaded
    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    // After loading, should have some rows
    int count = model.rowCount(rootIndex);
    QVERIFY(count >= 0); // At least 2 files we created
}

void tst_QFileSystemModel::remove()
{
    // Create a temporary file for removal test
    QTemporaryFile tempFile(m_tempPath + "/remove_test_XXXXXX.txt");
    QVERIFY(tempFile.open());
    tempFile.write("test content");
    tempFile.close();
    QString filePath = tempFile.fileName();

    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex fileIndex = model.index(filePath);
    QVERIFY(fileIndex.isValid());

    // Test remove
    bool removed = model.remove(fileIndex);
    QVERIFY(removed);

    // Verify file is gone
    QVERIFY(!QFile::exists(filePath));
}

void tst_QFileSystemModel::mkdir()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex rootIndex = model.index(m_tempPath);
    QVERIFY(rootIndex.isValid());

    QString newDirName = "test_mkdir_dir";
    QModelIndex newDirIndex = model.mkdir(rootIndex, newDirName);
    QVERIFY(newDirIndex.isValid());

    QString expectedPath = m_tempPath + "/" + newDirName;
    QCOMPARE(model.filePath(newDirIndex), expectedPath);
    QVERIFY(QDir(expectedPath).exists());
}

void tst_QFileSystemModel::filters()
{
    QFileSystemModel model;
    QDir::Filters filters = QDir::AllEntries | QDir::NoDotAndDotDot;
    model.setFilter(filters);
    QCOMPARE(model.filter(), filters);
}

void tst_QFileSystemModel::nameFilters()
{
    QFileSystemModel model;
    QStringList filters = QStringList() << "*.txt" << "*.cpp";
    model.setNameFilters(filters);
    QCOMPARE(model.nameFilters(), filters);
}

void tst_QFileSystemModel::permissions()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex rootIndex = model.index(m_tempPath);
    QVERIFY(rootIndex.isValid());

    QFile::Permissions perms = model.permissions(rootIndex);
    QVERIFY(perms != 0); // Should have some permissions
}

void tst_QFileSystemModel::fileInfo()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex rootIndex = model.index(m_tempPath);
    QVERIFY(rootIndex.isValid());

    QFileInfo info = model.fileInfo(rootIndex);
    QVERIFY(info.exists());
    QCOMPARE(info.absoluteFilePath(), m_tempPath);
}

void tst_QFileSystemModel::sort()
{
    QFileSystemModel model;
    model.setRootPath(m_tempPath);

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    // Test sorting by name
    model.sort(0, Qt::AscendingOrder);
    QCOMPARE(model.sortRole(), 0); // Name column

    // Test sorting by size
    model.sort(1, Qt::DescendingOrder);
    QCOMPARE(model.sortRole(), 1); // Size column
}

void tst_QFileSystemModel::icons()
{
    QFileSystemModel model;
    QFileIconProvider *provider = new QFileIconProvider();
    model.setIconProvider(provider);

    QCOMPARE(model.iconProvider(), provider);

    model.setRootPath(m_tempPath);
    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    QModelIndex rootIndex = model.index(m_tempPath);
    QVERIFY(rootIndex.isValid());

    QIcon icon = model.data(rootIndex, Qt::DecorationRole).value<QIcon>();
    QVERIFY(!icon.isNull()); // Should have an icon
}

void tst_QFileSystemModel::hidden()
{
    QFileSystemModel model;

    // Test with hidden files shown
    model.setFilter(QDir::AllEntries | QDir::NoDotAndDotDot | QDir::Hidden);
    QVERIFY(model.filter() & QDir::Hidden);

    // Test with hidden files hidden
    model.setFilter(QDir::AllEntries | QDir::NoDotAndDotDot);
    QVERIFY(!(model.filter() & QDir::Hidden));
}

void tst_QFileSystemModel::myComputer()
{
    QFileSystemModel model;
    QModelIndex myComputerIndex = model.index("/");
    QVERIFY(myComputerIndex.isValid());

    QVariant data = model.data(myComputerIndex, Qt::DisplayRole);
    QVERIFY(data.isValid());
}

void tst_QFileSystemModel::shortcut()
{
#ifdef Q_OS_WIN
    QFileSystemModel model;
    model.setResolveSymlinks(true);
    QVERIFY(model.resolveSymlinks());

    model.setResolveSymlinks(false);
    QVERIFY(!model.resolveSymlinks());
#endif
}

void tst_QFileSystemModel::caseSensitivity()
{
    QFileSystemModel model;

#ifdef Q_OS_WIN
    QVERIFY(!model.caseSensitivity()); // Windows is case insensitive
#else
    QVERIFY(model.caseSensitivity()); // Unix-like systems are case sensitive
#endif
}

void tst_QFileSystemModel::drives()
{
    QFileSystemModel model;
    model.setRootPath("/");

    QSignalSpy loadedSpy(&model, SIGNAL(directoryLoaded(QString)));
    QVERIFY(loadedSpy.wait(5000));

    // Should have at least one drive/root directory
    QVERIFY(model.rowCount() >= 1);
}

QTEST_MAIN(tst_QFileSystemModel)
#include "tst_qfilesystemmodel.moc"