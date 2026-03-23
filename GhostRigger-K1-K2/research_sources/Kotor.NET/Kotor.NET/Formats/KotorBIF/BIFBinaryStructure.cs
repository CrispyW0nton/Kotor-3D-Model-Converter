// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Extensions;

namespace Kotor.NET.Formats.KotorBIF
{
    public class BIFBinaryStructure
    {
        public class FileRoot
        {
            public FileHeader FileHeader { get; set; }
            public List<VariableResource> Resources { get; set; }

            public FileRoot(BinaryReader reader)
            {
                FileHeader = new FileHeader(reader);

                Resources = new List<VariableResource>();
                reader.BaseStream.Position = FileHeader.OffsetToResources;
                for (int i = 0; i < FileHeader.ResourceCount; i++)
                {
                    var resource = new VariableResource(reader);
                    Resources.Add(resource);
                }
            }
        }

        public class FileHeader
        {
            public string FileType { get; set; }
            public string FileVersion { get; set; }
            public int ResourceCount { get; set; }
            public int OffsetToResources { get; set; }

            public FileHeader(BinaryReader reader)
            {
                FileType = reader.ReadString(4);
                FileVersion = reader.ReadString(4);
                ResourceCount = reader.ReadInt32();
                reader.BaseStream.Position += 4;
                OffsetToResources = reader.ReadInt32();
            }
        }

        public class VariableResource
        {
            public uint ResourceID { get; set; }
            public int Offset { get; set; }
            public int FileSize { get; set; }
            public int ResourceType { get; set; }

            public VariableResource(BinaryReader reader)
            {
                ResourceID = reader.ReadUInt32();
                Offset = reader.ReadInt32();
                FileSize = reader.ReadInt32();
                ResourceType = reader.ReadInt32();
            }
        }
    }
}
