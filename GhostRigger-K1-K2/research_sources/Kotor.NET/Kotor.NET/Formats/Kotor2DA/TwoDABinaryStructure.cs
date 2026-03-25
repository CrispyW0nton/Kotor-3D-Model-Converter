using Kotor.NET.Extensions;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Kotor.NET.Formats.Kotor2DA
{
    internal class TwoDABinaryStructure
    {
        public class FileRoot
        {
            public FileHeader FileHeader { get; set; } = new();
            public List<string> ColumnHeaders { get; set; } = new();
            public List<string> RowHeaders { get; set; } = new();
            public List<string> CellValues { get; set; } = new();

            public FileRoot(BinaryReader reader)
            {
                FileHeader = new FileHeader(reader);

                while (reader.PeekChar() != '\0')
                {
                    var header = reader.ReadTerminatedString('\t');
                    ColumnHeaders.Add(header);
                }

                var nullTerminator = reader.ReadString(1);

                var rowCount = reader.ReadInt32();
                var cellCount = rowCount * ColumnHeaders.Count;
                for (int i = 0; i < rowCount; i++)
                {
                    var label = reader.ReadTerminatedString('\t');
                    RowHeaders.Add(label);
                }

                var uniqueCellOffsets = new List<int>();
                for (int i = 0; i < cellCount; i++)
                {
                    var cellOffset = reader.ReadUInt16();
                    uniqueCellOffsets.Add(cellOffset);
                }

                var cellDataSize = reader.ReadUInt16();
                var cellDataOffset = reader.BaseStream.Position;

                var uniqueCellValues = new Dictionary<int, string>();
                while (reader.BaseStream.Position != reader.BaseStream.Length)
                {
                    var offset = (int)(reader.BaseStream.Position - cellDataOffset);
                    var value = reader.ReadTerminatedString('\0');
                    uniqueCellValues.Add(offset, value);
                }

                var columnCount = ColumnHeaders.Count;
                for (int i = 0; i < rowCount * columnCount; i++)
                {
                    var offset = uniqueCellOffsets[i];
                    CellValues.Add(uniqueCellValues[offset]);
                }
            }

            public FileRoot()
            {

            }

            public void Write(BinaryWriter writer)
            {
                FileHeader.Write(writer);

                foreach (var columnHeader in ColumnHeaders)
                {
                    writer.Write(columnHeader, 0);
                    writer.Write("\t", 0);
                }

                writer.Write("\0", 0);

                writer.Write(RowHeaders.Count);
                foreach (var rowHeader in RowHeaders)
                {
                    writer.Write(rowHeader, 0);
                    writer.Write("\t", 0);
                }

                var uniqueCellValues = CellValues.ToHashSet();
                var uniqueCellOffsets = new Dictionary<string, int>();
                var uniqueCellOffset = 0;
                foreach (var cellValue in uniqueCellValues)
                {
                    uniqueCellOffsets.Add(cellValue, uniqueCellOffset);
                    uniqueCellOffset += cellValue.Length + 1;
                }

                foreach (var cellValue in CellValues)
                {
                    var offset = uniqueCellOffsets[cellValue];
                    writer.Write((ushort)offset);
                }

                var cellDataSize = uniqueCellOffsets.Sum(x => x.Value);
                writer.Write((ushort)cellDataSize);

                foreach (var value in uniqueCellOffsets.Keys)
                {
                    writer.Write(value + "\0", 0);
                }
            }
        }

        public class FileHeader
        {
            public string FileType { get; set; } = "2DA ";
            public string FileVersion { get; set; } = "v2.b";

            public FileHeader(BinaryReader reader)
            {
                FileType = reader.ReadString(4);
                FileVersion = reader.ReadString(4);
                var linebreak = reader.ReadString(1);
            }

            public FileHeader()
            {

            }

            public void Write(BinaryWriter writer)
            {
                writer.Write(FileType.PadRight(4).Truncate(4), 0);
                writer.Write(FileVersion.PadRight(4).Truncate(4), 0);
                writer.Write("\n", 0);
            }
        }
    }
}
