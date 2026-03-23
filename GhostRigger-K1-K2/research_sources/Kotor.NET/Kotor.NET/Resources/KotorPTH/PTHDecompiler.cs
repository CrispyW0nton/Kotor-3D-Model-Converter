using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Kotor.NET.Common;
using Kotor.NET.Formats.KotorGFF;
using Kotor.NET.Resources.KotorARE;

namespace Kotor.NET.Resources.KotorPTH
{
    public class PTHDecompiler : IGFFCompiler
    {
        public PTH _pth;

        public PTHDecompiler(PTH pth)
        {
            _pth = pth;
        }


        public GFF CompileGFF()
        {
            var gff = new GFF();

            var gffPathConnections = gff.Root.SetList("Path_Conections", new());
            var gffPathPoints = gff.Root.SetList("Path_Points", new());

            foreach (var point in _pth.Points)
            {
                var gffPathPoint = gffPathPoints.Add();

                gffPathPoint.SetSingle("X", point.X);
                gffPathPoint.SetSingle("Y", point.Y);
                gffPathPoint.SetUInt32("First_Conection", (uint)gffPathConnections.Count);

                foreach (var connection in point.Connections)
                {
                    var gffPathConnection = gffPathConnections.Add();

                    gffPathConnection.SetUInt32("Destination", (uint)_pth.Points.IndexOf(connection));
                }
            }

            return gff;
        }
    }
}
