using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;

namespace Kotor.NET.Resources.KotorPTH
{
    public class PTHCompiler : IGFFDecompiler<PTH>
    {
        private GFF _gff;

        public PTHCompiler(GFF gff)
        {
            _gff = gff ?? throw new ArgumentNullException(nameof(gff));
        }

        public PTH Decompile()
        {
            var pth = new PTH();

            var pathConnetionsList = _gff.Root.GetList("Path_Conections", new());
            var pathPointsList = _gff.Root.GetList("Path_Points", new());

            pth.Points = new List<PathPoint>(new PathPoint[pathPointsList.Count]);

            for (var i = 0; i < pathPointsList.Count; i ++)
            {
                var pathPointStruct = pathPointsList.Get(i);
                var point = pth.Points[i];

                point.X = pathPointStruct.GetSingle("X", 0);
                point.Y = pathPointStruct.GetSingle("Y", 0);

                var connectionCount = pathPointStruct.GetUInt32("Conections", 0);
                var firstConnectionIndex = (int)pathPointStruct.GetUInt32("First_Conection", 0);
                for (int j = 0; j < connectionCount; j ++)
                {
                    var destinationIndex = (int)pathConnetionsList.Get(firstConnectionIndex + 1).GetUInt32("Destination", 0);
                    point.Connections.Add(pth.Points[destinationIndex]);
                }
            }

            return pth;
        }
    }
}
