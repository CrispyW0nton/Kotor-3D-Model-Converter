// Licensed to the .NET Foundation under one or more agreements.
// The .NET Foundation licenses this file to you under the MIT license.

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Formats.KotorGFF;
using static Kotor.NET.Formats.KotorTLK.TLKBinaryStructure;

namespace Kotor.NET.Formats.KotorTLK
{
    public class TLKBinaryWriter
    {
        public BinaryWriter? _writer;
        public TLK? _tlk;

        public TLKBinaryWriter(string filepath)
        {
            _writer = new BinaryWriter(new FileStream(filepath, FileMode.OpenOrCreate));
        }
        public TLKBinaryWriter(Stream stream)
        {
            _writer = new BinaryWriter(stream);
        }

        public void Write(TLK tlk)
        {
            _tlk = tlk;

            var root = new FileRoot();

            root.FileHeader = new FileHeader
            {
                FileType = "TLK ",
                FileVersion = "V3.0",
                LanguageID = (int)tlk.Language,
                StringCount = tlk.Entries.Count,
                StringEntriesOffset = FileHeader.SIZE + (StringData.SIZE * tlk.Entries.Count),
            };

            var offsetToString = 0;
            foreach (var entry in tlk.Entries)
            {
                root.StringData.Add(new StringData
                {
                    Flags = 0,
                    SoundResRef = entry.ResRef,
                    VolumeVariance = 0,
                    PitchVariance = 0,
                    OffsetToString = offsetToString,
                    StringSize = entry.Text.Length,
                    Length = 0.0f,
                });

                root.StringEntries.Add(entry.Text);
                offsetToString += entry.Text.Length;
            }

            root.Write(_writer);
        }
    }
}
