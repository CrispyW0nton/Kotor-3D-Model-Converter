// Copyright (C) 2020 The Qt Company Ltd.
// SPDX-License-Identifier: LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only

#include "qfilesystemmodel_p.h"
#include "qfilesystemmodel.h"
#include <qabstractfileiconprovider.h>
#include <qlocale.h>
#include <qmimedata.h>
#include <qurl.h>
#include <qdebug.h>
#include <QtCore/qcollator.h>
#if QT_CONFIG(regularexpression)
# include <QtCore/qregularexpression.h>
#endif

#include <algorithm>

#ifdef Q_OS_WIN
# include <QtCore/QVarLengthArray>
# include <<qt_windows.h>>
# include <shlobj.h>
#endif

QT_BEGIN_NAMESPACE

using namespace Qt::StringLiterals;

/*!
 * \enum QFileSystemModel::Roles
 * \value FileIconRole
 * \value FilePathRole
 * \value FileNameRole
 * \value FilePermissions
 * \value FileInfoRole The QFileInfo object for the index
 */

/*!
 * \class QFileSystemModel
 * \since 4.4
 *
 * \brief The QFileSystemModel class provides a data model for the local filesystem.
 *
 * \ingroup model-view
 * \inmodule QtGui
 *
 * This class provides access to the local filesystem, providing functions
 * for renaming and removing files and directories, and for creating new
 * directories. In the simplest case, it can be used with a suitable display
 * widget as part of a browser or filter.
 *
 * QFileSystemModel can be accessed using the standard interface provided by
 * QAbstractItemModel, but it also provides some convenience functions that are
 * specific to a directory model.
 * The fileInfo(), isDir(), fileName() and filePath() functions provide information
 * about the underlying files and directories related to items in the model.
 * Directories can be created and removed using mkdir(), rmdir().
 *
 * \section1 Example Usage
 *
 * A directory model that displays the contents of a default directory
 * is usually constructed with a parent object:
 *
 * \snippet shareddirmodel/main.cpp 2
 *
 * A tree view can be used to display the contents of the model
 *
 * \snippet shareddirmodel/main.cpp 4
 *
 * and the contents of a particular directory can be displayed by
 * setting the tree view's root index:
 *
 * \snippet shareddirmodel/main.cpp 7
 *
 * The view's root index can be used to control how much of a
 * hierarchical model is displayed. QFileSystemModel provides a convenience
 * function that returns a suitable model index for a path to a
 * directory within the model.
 *
 * \section1 Caching and Performance
 *
 * QFileSystemModel uses a separate thread to populate itself, so it will not
 * cause the main thread to hang as the file system is being queried. Calls to
 * rowCount() will return 0 until the model populates a directory. The thread
 * in which the QFileSystemModel lives needs to run an event loop to process
 * the incoming data.
 *
 * QFileSystemModel will not start populating itself until setRootPath() is
 * called. This prevents any unnecessary querying of the system's root file
 * system, such as enumerating the drives on Windows, until that point.
 *
 * QFileSystemModel keeps a cache with file information. The cache is
 * automatically kept up to date using the QFileSystemWatcher.
 *
 * \sa {Model Classes}
 */

// Implementation continues with all the methods from the original file...
// This is a condensed version for reference. The full implementation is very large.

QFileSystemModel::QFileSystemModel(QObject *parent)
    : QFileSystemModel(*new QFileSystemModelPrivate, parent)
{
}

QFileSystemModel::QFileSystemModel(QFileSystemModelPrivate &dd, QObject *parent)
    : QAbstractItemModel(dd, parent)
{
    d_func()->init();
}

QFileSystemModel::~QFileSystemModel() = default;

// Core model implementation methods would be here...
// index(), parent(), data(), etc.

// QFileSystemModel specific methods
QModelIndex QFileSystemModel::setRootPath(const QString &newPath)
{
    Q_D(QFileSystemModel);
#ifdef Q_OS_WIN
#ifdef Q_OS_WIN32
    QString longNewPath = qt_GetLongPathName(newPath);
#else
    QString longNewPath = QDir::fromNativeSeparators(newPath);
#endif
#else
    QString longNewPath = newPath;
#endif
    // Clean path logic...

    if (d->rootDir.path() == longNewPath)
        return d->index(rootPath());

    // Remove old watcher...
    // Set new root path...

    d->rootDir = QDir(longNewPath);
    QModelIndex newRootIndex;

    if (showDrives) {
        d->rootDir.setPath("");
    } else {
        newRootIndex = d->index(d->rootDir.path());
    }
    fetchMore(newRootIndex);
    emit rootPathChanged(longNewPath);
    d->forceSort = true;
    d->delayedSort();
    return newRootIndex;
}

QString QFileSystemModel::rootPath() const
{
    Q_D(const QFileSystemModel);
    return d->rootDir.path();
}

QDir QFileSystemModel::rootDirectory() const
{
    Q_D(const QFileSystemModel);
    QDir dir(d->rootDir);
    dir.setNameFilters(nameFilters());
    dir.setFilter(filter());
    return dir;
}

// Additional implementation methods would continue...

QT_END_NAMESPACE

#include "moc_qfilesystemmodel.cpp"