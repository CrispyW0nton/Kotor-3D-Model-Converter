using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Extensions;

namespace Kotor.NET.Formats.KotorSSF
{
    public class SSFBinaryStructure
    {
        public class FileRoot
        {
            public FileHeader FileHeader { get; set; } = new();
            public SoundTable SoundTable { get; set; } = new();

            public FileRoot()
            {

            }

            public FileRoot(BinaryReader reader)
            {
                FileHeader = new(reader);

                reader.BaseStream.Position = FileHeader.OffsetToSounds;
                SoundTable = new(reader);
            }

            public void Write(BinaryWriter writer)
            {
                FileHeader.Write(writer);
                SoundTable.Write(writer);
            }
        }

        public class FileHeader
        {
            public string FileType { get; set; }
            public string FileVersion { get; set; }
            public int OffsetToSounds { get; set; }

            public FileHeader()
            {
                FileType = "SSF ";
                FileVersion = "V1.1";
                OffsetToSounds = 12;
            }

            public FileHeader(BinaryReader reader)
            {
                FileType = reader.ReadString(4);
                FileVersion = reader.ReadString(4);
                OffsetToSounds = reader.ReadInt32();
            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(FileType, 0);
                writer.Write(FileVersion, 0);
                writer.Write(OffsetToSounds);
            }
        }

        public class SoundTable
        {
            public int[] SoundStringRefs = new int[40]; 

            public SoundTable()
            {

            }

            public SoundTable(BinaryReader reader)
            {
                for (int i = 0; i < 40; i ++)
                {
                    SoundStringRefs[i] = reader.ReadInt32();
                }
            }

            public void Write(BinaryWriter writer)
            {
                for (int i = 0; i < 40; i ++)
                {
                    writer.Write(SoundStringRefs[i]);
                }
            }
        }
    }
}
