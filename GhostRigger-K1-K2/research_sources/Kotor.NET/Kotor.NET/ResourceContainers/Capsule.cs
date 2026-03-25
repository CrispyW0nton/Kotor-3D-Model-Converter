using Kotor.NET.Common.Data;
using Kotor.NET.Extensions;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.ResourceContainers
{
    /// <summary>
    /// Provides easy access to resource in RIM and MOD-like files. Files are opened to
    /// build a list of ResourceReferences but no resource data is actually stored in
    /// memory.
    /// </summary>
    public class Capsule : IResourceContainer
    {
        /// <summary>
        /// Filepath to the capsule.
        /// </summary>
        public string FilePath { get; private set; }

        private List<ResourceReference> _references;

        public Capsule(string filepath)
        {
            FilePath = filepath;
            _references = new List<ResourceReference>();

            Reload();
        }

        public Resource Get(ResRef resref, ResourceType type, bool reload = false)
        {
            var reference = Locate(resref, type, reload);
            var data = reference.FetchData();
            return new Resource(reference.ResRef, reference.ResourceType, data);
        }

        public ResourceReference Locate(ResRef resref, ResourceType type, bool reload = false)
        {
            var reference = _references.SingleOrDefault(x => x.ResRef == resref && x.ResourceType == type);

            if (reference == null)
            {
                throw new ArgumentException($"Resource '{resref}.{type}' does not exist.");
            }
            else
            {
                return reference;
            }
        }

        public IReadOnlyList<ResourceReference> All()
        {
            return new ReadOnlyCollection<ResourceReference>(_references);
        }

        /// <summary>
        /// Refreshes the cached list of ResourceReferences
        /// </summary>
        /// <exception cref="ArgumentException">Capsule is pointing towards an invalid filepath.</exception>
        public void Reload()
        {
            _references.Clear();

            using (var stream = File.OpenRead(FilePath))
            using (var reader = new BinaryReader(stream))
            {
                if (FilePath.EndsWith("RIM", StringComparison.OrdinalIgnoreCase))
                {
                    LoadRIM(reader);
                }
                else if (FilePath.EndsWith("MOD", StringComparison.OrdinalIgnoreCase) || FilePath.EndsWith("ERF", StringComparison.OrdinalIgnoreCase))
                {
                    LoadERF(reader);
                }
                else
                {
                    throw new ArgumentException("Tried to load non-ERF and non-RIM capsule.");
                }
            }
        }

        private void LoadERF(BinaryReader reader)
        {
            _references.Clear();

            reader.BaseStream.Position = 8;
            var entryCount = reader.ReadInt32();
            reader.BaseStream.Position += 4;
            var offsetToKeys = reader.ReadInt32();
            var offsetToResources = reader.ReadInt32();

            var keys = new List<Tuple<ResRef, ResourceType>>();
            reader.BaseStream.Position = offsetToKeys;
            for (int i = 0; i < entryCount; i++)
            {
                var resref = new ResRef(reader.ReadString(16));
                var resourceID = reader.ReadInt32();
                var resourceType = ResourceType.ByID(reader.ReadUInt16());

                var key = new Tuple<ResRef, ResourceType>(resref, resourceType);
                keys.Add(key);
            }

            reader.BaseStream.Position = offsetToResources;
            foreach (var key in keys)
            {
                var offset = reader.ReadInt32();
                var size = reader.ReadInt32();

                var reference = new ResourceReference(FilePath, key.Item1, key.Item2, offset, size);
                _references.Add(reference);
            }
        }

        private void LoadRIM(BinaryReader reader)
        {
            _references.Clear();

            reader.BaseStream.Position = 4;
            var entryCount = reader.ReadInt32();
            var offsetToEntries = reader.ReadInt32();

            reader.BaseStream.Position = offsetToEntries;
            for (int i = 0; i < entryCount; i++)
            {
                var resref = new ResRef(reader.ReadString(16));
                var resourceType = ResourceType.ByID(reader.ReadInt32()); // TODO uint
                var resourceID = reader.ReadInt32();
                var offset = reader.ReadInt32();
                var size = reader.ReadInt32();

                var reference = new ResourceReference(FilePath, resref, resourceType, offset, size);
                _references.Add(reference);
            }
        }
    }
}
