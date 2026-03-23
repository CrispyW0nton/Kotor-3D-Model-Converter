using Kotor.NET.Common.Data;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.ResourceContainers
{
    /// <summary>
    /// Gives access to resources.
    /// </summary>
    public interface IResourceContainer
    {
        /// <summary>
        /// Returns a ResourceResource for the specified resource if it is present,
        /// otherwise returns null.
        /// </summary>
        /// <param name="resref">The resource identifier.</param>
        /// <param name="resourceType">The resource file type.</param>
        /// <param name="reload">Reload the container's cache before trying to locate
        /// the resource.</param>
        /// <returns></returns>
        public ResourceReference? Locate(ResRef resref, ResourceType resourceType, bool reload = false);

        /// <summary>
        /// Returns a specified resource in the container if it is present, otherwise
        /// returns null.
        /// </summary>
        /// <param name="resref">The resource identifier.</param>
        /// <param name="resourceType">The resource file type.</param>
        /// <param name="reload">Reload the container's cache before trying to load the
        /// resource.</param>
        /// <returns></returns>
        public Resource? Get(ResRef resref, ResourceType resourceType, bool reload = false);

        public IReadOnlyList<ResourceReference> All();
    }
}
