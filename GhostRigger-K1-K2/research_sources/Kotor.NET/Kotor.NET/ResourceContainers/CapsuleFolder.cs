using Kotor.NET.Common.Data;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.ResourceContainers
{
    public class CapsuleFolder : IResourceContainer
    {
        public string Path { get; private set; }

        private List<Capsule> _capsules;

        public CapsuleFolder(string path)
        {
            Path = path;
            _capsules = new List<Capsule>();

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

            var reference = _capsules.Select(x => x.Locate(resref, type)).FirstOrDefault();

            if (reference == null)
            {
                throw new ArgumentException($"Resource '{resref}.{type}' does not exist.");
            }
            else
            {
                return reference;
            }
        }

        public void Reload()
        {
            _capsules.Clear();

            foreach (var filepath in Directory.GetFiles(Path))
            {
                var capsule = new Capsule(filepath);
                _capsules.Add(capsule);
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

        public IReadOnlyList<ResourceReference> All() => throw new NotImplementedException();
    }
}
