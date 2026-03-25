using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.ResourceContainers;

namespace Kotor.NET.Common.Data
{
    public class ResourceReference
    {
        public Uri Uri { get; private set; }
        public ResourceType ResourceType { get; private set; }
        public ResRef ResRef { get; private set; }
        public int Size { get; private set; }
        public int Offset { get; private set; }

        public string FileName { get => ResRef.Get() + "." + ResourceType.Extension; }

        /// <summary>
        /// Initialize a ResourceReference for a specified file. The file size is will
        /// be determined from the path.
        /// </summary>
        /// <param name="filepath">Path to the resource.</param>
        public ResourceReference(string filepath)
        {
            Uri = new Uri(filepath);
            ResRef = Path.GetFileNameWithoutExtension(filepath);
            ResourceType = ResourceType.ByExtension(Path.GetExtension(filepath));
            Size = (int)new FileInfo(filepath).Length;
            Offset = 0;
        }

        /// <summary>
        /// Initiaze a ResourceReference for a resource that is contained within a RIM
        /// or ERF-like file. The resource size and offset will be determined from the
        /// container.
        /// </summary>
        /// <param name="filepath">Path to the resource container.</param>
        /// <param name="resref">The resource identifier.</param>
        /// <param name="resourceType">The resource file type.</param>
        /// <exception cref="FileNotFoundException">Could not find the specified
        /// file.</exception>
        public ResourceReference(string filepath, ResRef resref, ResourceType resourceType)
        {
            Uri = new Uri(filepath);
            ResRef = resref;
            ResourceType = resourceType;

            // TODO
            IResourceContainer container = null;
            var reference = container.Locate(resref, ResourceType);

            if (reference != null)
            {
                Size = reference.Size;
                Offset = reference.Offset;
            }
            else
            {
                throw new FileNotFoundException($"Could not find file at ${filepath}");
            }
        }

        /// <summary>
        /// Initializes a ResourceReference with the given arguments.
        /// </summary>
        /// <param name="filepath">The file path to where the resource is stored.</param>
        /// <param name="resref">The resource identifier.</param>
        /// <param name="resourceType">The resource file type.</param>
        /// <param name="size">The size of the resource in bytes.</param>
        /// <param name="offset">The offset into file where the resource is present.</param>
        public ResourceReference(string filepath, ResRef resref, ResourceType resourceType, int size, int offset)
        {
            Uri = new Uri(filepath);
            ResRef = resref;
            ResourceType = resourceType;
            Size = size;
            Offset = offset;
        }

        /// <summary>
        /// Access the file at the Uri and Returns the data.
        /// </summary>
        /// <returns></returns>
        public byte[] FetchData()
        {
            using (var stream = File.OpenRead(Uri.LocalPath))
            using (var reader = new BinaryReader(stream))
            {
                reader.BaseStream.Position = Offset;
                var data = reader.ReadBytes(Size);

                return data;
            }
        }

        public override int GetHashCode()
        {
            return Uri.GetHashCode();
        }
    }
}
