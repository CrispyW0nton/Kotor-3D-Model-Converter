using System;
using System.Collections.Generic;
using System.Linq;
using System.Numerics;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Common.Data
{
    public class Resource
    {
        public ResRef ResRef { get; init; }
        public ResourceType Type { get; init; }
        public byte[] Data { get; init; }

        public Resource(ResRef resRef, ResourceType type, byte[] data)
        {
            ResRef = resRef;
            Type = type;
            Data = data;
        }
    }
}
