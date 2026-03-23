using Kotor.NET.Common.Data;
using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.ResourceContainers
{
    /// <summary>
    /// Provides access to list of ResourceReferences to a specified folder on the
    /// user's filesystem.
    /// </summary>
    public class ResourceFolder : IResourceContainer
    {
        public string Path { get; }

        private List<ResourceReference> _references = new();

        public ResourceFolder(string path)
        {
            Path = path;

            Reload();
        }

        public Resource Get(ResRef resref, ResourceType type, bool reload = false)
        {
            var reference = Locate(resref, type, reload);
            return GetReferenceData(reference);
        }

        public ResourceReference Locate(ResRef resref, ResourceType type, bool reload = false)
        {
            if (reload)
                Reload();

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
        /// Reload the list of files from the stored path.
        /// </summary>
        public void Reload()
        {
            _references.Clear();

            var files = new DirectoryInfo(Path).GetFiles("*.*", SearchOption.AllDirectories);
            foreach (var file in files)
            {
                var resref = new ResRef(System.IO.Path.GetFileNameWithoutExtension(file.Name));
                var type = ResourceType.ByExtension(file.Extension);
                var reference = new ResourceReference(file.FullName, resref, type, 0, (int)file.Length);
                _references.Add(reference);
            }
        }

        private Resource GetReferenceData(ResourceReference reference)
        {
            using (var stream = File.OpenRead(reference.Uri.LocalPath))
            using (var reader = new BinaryReader(stream))
            {
                reader.BaseStream.Position = reference.Offset;
                var data = reader.ReadBytes(reference.Size);

                return new Resource(reference.ResRef, reference.ResourceType, data);
            }
        }
    }
}
