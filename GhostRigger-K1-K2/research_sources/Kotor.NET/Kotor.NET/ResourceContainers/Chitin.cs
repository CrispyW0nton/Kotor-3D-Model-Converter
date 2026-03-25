// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorBIF;
using Kotor.NET.Formats.KotorKEY;

namespace Kotor.NET.ResourceContainers
{
    public class Chitin : IResourceContainer
    {
        public string GameDirectory { get; private set; }

        private List<ResourceReference> _references;

        public Chitin(string directory)
        {
            GameDirectory = directory;
            _references = new();

            Reload();
        }

        public ResourceReference? Locate(ResRef resref, ResourceType resourceType, bool reload = false) => throw new NotImplementedException();

        public Resource? Get(ResRef resref, ResourceType resourceType, bool reload = false) => throw new NotImplementedException();

        public IReadOnlyList<ResourceReference> All()
        {
            return new ReadOnlyCollection<ResourceReference>(_references);
        }

        public void Reload()
        {
            _references.Clear();

            var chitinPath = Path.Join(GameDirectory, "chitin.key");
            var chitinReader = new BinaryReader(File.OpenRead(chitinPath));
            var chitinFile = new KEYBinaryStructure.FileRoot(chitinReader);

            foreach (var bifFilename in chitinFile.Filenames)
            {
                var bifPath = Path.Join(GameDirectory, bifFilename);
                var bifReader = new BinaryReader(File.OpenRead(bifPath));
                var bifFile = new BIFBinaryStructure.FileRoot(bifReader);

                foreach (var bifResource in bifFile.Resources)
                {
                    var chitinKey = chitinFile.Keys.Single(x => x.ResourceID == bifResource.ResourceID);

                    var resref = new ResRef(chitinKey.ResRef);
                    var resourceType = ResourceType.ByID(chitinKey.ResourceType);
                    var offset = bifResource.Offset;
                    var size = bifResource.FileSize;

                    var reference = new ResourceReference(bifPath, resref, resourceType, offset, size);
                    _references.Add(reference);
                }
            }
        }

    }
}
