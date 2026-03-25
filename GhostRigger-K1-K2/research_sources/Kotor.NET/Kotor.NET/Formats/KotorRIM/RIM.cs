using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common.Data;
using Kotor.NET.Formats.KotorERF;

namespace Kotor.NET.Formats.KotorRIM
{
    public class RIM
    {
        public List<Resource> Resources { get; set; }

        public RIM()
        {
            Resources = new();
        }

        public Resource? Get(ResRef ResRef, ResourceType ResType)
        {
            return Resources.FirstOrDefault(x => x.ResRef == ResRef && x.Type == ResType);
        }
    }
}
